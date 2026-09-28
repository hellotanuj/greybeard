"""Greybeard's memory layer: everything that touches Hindsight lives here.

How memory is organised
-----------------------
* One bank per service organisation ("greybeard-fleet"). Every closed work order,
  every failed fix, every site rule is retained into it.
* Every memory is tagged along the axes a technician actually thinks in:
  ``asset:ORB-CH-02``, ``model:kryo-acx-500``, ``site:orbit``, ``type:chiller``,
  ``tech:ravi``, ``outcome:not_fixed``. Tags let recall zoom from "this exact
  unit" out to "every unit of this model in the fleet".
* A second bank ("greybeard-day1") has the identical configuration and no
  history. It powers the honest before/after comparison in the UI.
* Hindsight consolidates the raw work orders into *observations* in the
  background (e.g. "ACX-500 A-140 repeats on one circuit with clean coils ->
  fan VFD derating"). *Mental models* sit on top as living "fleet knowledge"
  pages that rewrite themselves after each consolidation.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from hindsight_client import Hindsight

from .config import settings

log = logging.getLogger("greybeard.memory")

# --------------------------------------------------------------------------- bank profile
RETAIN_MISSION = (
    "This bank belongs to a commercial building maintenance company. Extract: equipment faults and alarm codes; "
    "measured readings; the root cause; the fix that worked; fixes that were tried and did NOT work (and why); "
    "parts used and their cost; site access rules and safety constraints; customer/facility-manager preferences; "
    "which technician did what. Always preserve work order IDs (WO-xxxx-xxx), asset IDs (e.g. ORB-CH-02), "
    "equipment models and serial-number batches verbatim."
)

OBSERVATIONS_MISSION = (
    "Consolidate durable field-service knowledge: recurring failure patterns per equipment model, serial batch and "
    "asset; diagnostic shortcuts that save time; fixes that repeatedly failed; seasonal patterns (summer heat, "
    "monsoon); site access rules; customer communication preferences; technician expertise. Keep work order IDs "
    "as evidence."
)

REFLECT_MISSION = (
    "You are Greybeard, the most experienced field-service engineer at Deccan Facility Services, a company "
    "maintaining chillers, DG sets, lifts, UPS systems and AHUs across Hyderabad's IT corridor. You brief "
    "technicians before they walk into a plant room. You are practical and specific: you name the check that "
    "takes 10 minutes before the fix that takes 4 hours, you warn about fixes that have failed before, and you "
    "cite work order IDs for every claim that comes from history. If memory has nothing relevant, say so plainly "
    "and fall back to standard OEM practice, clearly labelled as generic."
)

DIRECTIVES = [
    ("cite-evidence", "Every claim based on past jobs must cite the supporting work order IDs (WO-xxxx-xxx).", 10),
    ("flag-failed-fixes", "If a fix was tried before on this asset or model and did not solve the problem, explicitly warn the technician not to repeat it and say what worked instead.", 9),
    ("prefer-recent", "When older and newer memories about the same asset conflict (e.g. equipment was replaced, retrofitted or reset), trust the most recent state and explicitly list the older advice as superseded.", 9),
    ("safety-first", "Always remind the technician to apply lockout/tagout before working on electrical or rotating equipment.", 8),
]

# Living "Fleet Knowledge" pages. Hindsight rewrites them after each consolidation.
MENTAL_MODELS = [
    ("failure-patterns", "Recurring failure patterns",
     "What recurring failure patterns exist across the fleet, grouped by equipment model? For each: symptom/alarm, "
     "real root cause, fastest diagnostic check, the fix that works, and supporting work order IDs."),
    ("failed-fixes", "Fixes that didn't work",
     "Which fixes were tried and failed to solve the problem? For each: asset, what was tried, the cost/time wasted, "
     "what the real cause turned out to be, and work order IDs."),
    ("site-playbook", "Site access & customer playbook",
     "For each site: access rules, permits, safety constraints, timing restrictions and facility manager "
     "communication preferences a technician must know before arriving."),
    ("expertise-map", "Who knows what",
     "Which technicians have solved which kinds of problems? Who should a junior technician call for each "
     "equipment type or failure pattern, and why?"),
]

BRIEFING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "One sentence: the single most important thing to know walking in."},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "check_first": {
            "type": "array",
            "description": "Ordered diagnostic steps, fastest/highest-yield first.",
            "items": {
                "type": "object",
                "properties": {
                    "step": {"type": "string"},
                    "why": {"type": "string"},
                    "minutes": {"type": "integer"},
                    "evidence": {"type": "array", "items": {"type": "string"}, "description": "Work order IDs"},
                },
                "required": ["step", "why"],
            },
        },
        "likely_causes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "cause": {"type": "string"},
                    "likelihood": {"type": "integer", "description": "0-100"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["cause", "likelihood"],
            },
        },
        "avoid": {
            "type": "array",
            "description": "Fixes that were tried before and did not work.",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "why": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["action", "why"],
            },
        },
        "superseded": {
            "type": "array",
            "description": "Past advice that USED to be right for this asset but is now obsolete because something changed later (retrofit, replacement, reset, new procedure). Empty if none.",
            "items": {
                "type": "object",
                "properties": {
                    "old_advice": {"type": "string"},
                    "why_obsolete": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["old_advice", "why_obsolete"],
            },
        },
        "parts_to_carry": {"type": "array", "items": {"type": "string"}},
        "site_notes": {"type": "array", "items": {"type": "string"}},
        "call_if_stuck": {
            "type": "array",
            "items": {"type": "object", "properties": {"name": {"type": "string"}, "why": {"type": "string"}}, "required": ["name", "why"]},
        },
    },
    "required": ["headline", "confidence", "check_first", "likely_causes"],
}

WO_RE = re.compile(r"WO-\d{4}-\d{3}")


# --------------------------------------------------------------------------- helpers
def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def to_dict(obj: Any) -> Any:
    """Normalise generated-client models / lists into plain JSON-able data."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_dict(v) for v in obj]
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return str(obj)


def items_of(resp: Any) -> list[dict]:
    """List endpoints return either a bare list or {"items": [...]}; accept both."""
    data = to_dict(resp)
    if isinstance(data, dict):
        data = data.get("items") or data.get("mental_models") or data.get("directives") or []
    return [d for d in (data or []) if isinstance(d, dict)]


def tags_for(job: dict, asset: dict) -> list[str]:
    tags = [
        f"asset:{job['asset_id']}",
        f"site:{asset.get('site', job.get('site', 'unknown'))}",
        f"type:{asset.get('type', 'unknown')}",
        f"model:{slug(asset.get('model', 'unknown'))}",
        f"outcome:{job.get('outcome', 'unknown')}",
    ]
    if job.get("technician"):
        tags.append(f"tech:{job['technician']}")
    return tags


def render_job(job: dict, asset: dict, site: dict, tech: dict) -> str:
    """Render a work order as the narrative a senior tech would write in a logbook."""
    outcome_label = {
        "fixed": "RESOLVED",
        "not_fixed": "NOT RESOLVED (problem came back / root cause not found)",
        "false_alarm": "RESOLVED (false alarm: instrument fault)",
        "pm": "PLANNED MAINTENANCE",
        "advisory": "ADVISORY / PREVENTIVE",
    }.get(job.get("outcome", ""), job.get("outcome", ""))
    lines = [
        f"Work order {job['wo_id']} | {asset.get('id', job['asset_id'])} ({asset.get('model', '?')}, serial {asset.get('serial', '?')}) "
        f"at {site.get('name', job.get('site'))}, {site.get('locality', '')}.",
        f"Technician: {tech.get('name', job.get('technician'))}. Opened {job['opened_at'][:16].replace('T', ' ')}.",
    ]
    if job.get("alarm_code"):
        lines.append(f"Alarm: {job['alarm_code']}.")
    lines += [
        f"Reported symptom: {job['symptom']}",
        f"Technician notes: {job['notes']}",
        f"Root cause: {job.get('root_cause', 'n/a')}. Outcome: {outcome_label}.",
    ]
    if job.get("parts"):
        lines.append("Parts used: " + ", ".join(job["parts"]) + ".")
    if job.get("downtime_hours"):
        lines.append(f"Equipment downtime: {job['downtime_hours']} h.")
    return "\n".join(lines)


def job_to_item(job: dict, catalog) -> dict:
    asset = catalog.assets.get(job["asset_id"], {})
    site = catalog.sites.get(asset.get("site", ""), {})
    tech = catalog.techs.get(job.get("technician", ""), {})
    return {
        "content": render_job(job, asset, site, tech),
        "timestamp": datetime.fromisoformat(job.get("closed_at") or job["opened_at"]),
        "context": f"field service work order ({job.get('kind', 'corrective')})",
        "document_id": job["wo_id"],
        "metadata": {"wo_id": job["wo_id"], "asset_id": job["asset_id"], "outcome": str(job.get("outcome", ""))},
        "tags": tags_for(job, asset),
    }


# --------------------------------------------------------------------------- memory service
class FleetMemory:
    def __init__(self, client: Hindsight | None = None) -> None:
        self.client = client or Hindsight(base_url=settings.hindsight_base_url, api_key=settings.hindsight_api_key, timeout=180)
        self.fleet = settings.fleet_bank
        self.day1 = settings.day1_bank

    # ---------------------------------------------------------------- setup
    async def configure_bank(self, bank_id: str) -> None:
        await self.client.acreate_bank(bank_id, reflect_mission=REFLECT_MISSION, retain_mission=RETAIN_MISSION,
                                       observations_mission=OBSERVATIONS_MISSION, enable_observations=True)
        try:
            await self.client.aupdate_bank_config(bank_id, disposition_skepticism=4, disposition_literalism=3, disposition_empathy=2)
        except Exception as e:  # older servers: dispositions via create_bank only
            log.warning("disposition update skipped: %s", e)
        existing = {d.get("name") for d in items_of(await self.client.alist_directives(bank_id))}
        for name, content, prio in DIRECTIVES:
            if name not in existing:
                await self.client.acreate_directive(bank_id, name=name, content=content, priority=prio)

    async def ensure_mental_models(self, bank_id: str) -> None:
        existing = {m.get("id") for m in await self.mental_models(bank_id)}
        for mid, name, query in MENTAL_MODELS:
            if mid not in existing:
                await self.client.acreate_mental_model(
                    bank_id, id=mid, name=name, source_query=query,
                    trigger={"refresh_after_consolidation": True, "mode": "delta"},
                )

    # ---------------------------------------------------------------- retain
    async def retain_jobs(self, jobs: list[dict], catalog, bank_id: str | None = None, retain_async: bool = True) -> dict:
        items = [job_to_item(j, catalog) for j in jobs]
        resp = await self.client.aretain_batch(bank_id or self.fleet, items=items, retain_async=retain_async)
        return to_dict(resp)

    async def retain_site_knowledge(self, catalog, bank_id: str | None = None) -> None:
        items = []
        for s in catalog.sites.values():
            items.append({
                "content": f"Site profile: {s['name']} ({s['locality']}). Facility manager: {s['facility_manager']}. " + " ".join(s["notes"]),
                "context": "site access & customer profile", "document_id": f"site-{s['id']}",
                "tags": [f"site:{s['id']}", "kind:site-profile"],
            })
        for t in catalog.techs.values():
            items.append({
                "content": f"Technician profile: {t['name']}, {t['role']}, {t['years']} years experience. {t.get('note', '')}",
                "context": "technician profile", "document_id": f"tech-{t['id']}", "tags": [f"tech:{t['id']}", "kind:tech-profile"],
            })
        await self.client.aretain_batch(bank_id or self.fleet, items=items, retain_async=True)

    # ---------------------------------------------------------------- recall (the "memory inspector")
    async def recall_for_ticket(self, ticket: dict, bank_id: str | None = None) -> dict:
        """Two lenses, shown side by side in the UI: this exact unit vs the whole fleet."""
        asset = ticket["asset"]
        query = f"{ticket.get('alarm_code') or ''} {ticket['symptom']} {asset.get('model', '')}".strip()
        bank = bank_id or self.fleet
        asset_hits = await self.client.arecall(bank, query, tags=[f"asset:{asset['id']}"], tags_match="any_strict",
                                               types=["world", "experience", "observation"], budget="mid", max_tokens=2500)
        fleet_hits = await self.client.arecall(bank, query, tags=[f"model:{slug(asset.get('model', ''))}", f"site:{asset.get('site')}"],
                                               tags_match="any_strict", types=["observation", "world", "experience"],
                                               budget="mid", max_tokens=2500)
        return {"asset": self._hits(asset_hits), "fleet": self._hits(fleet_hits), "query": query}

    @staticmethod
    def _hits(resp: Any) -> list[dict]:
        out = []
        for r in (to_dict(resp) or {}).get("results", []) or []:
            out.append({
                "id": r.get("id"), "text": r.get("text"), "type": r.get("type"),
                "when": r.get("occurred_start") or r.get("mentioned_at"),
                "document_id": r.get("document_id"), "tags": r.get("tags") or [],
                "wo_ids": sorted(set(WO_RE.findall((r.get("text") or "") + " " + (r.get("document_id") or "")))),
            })
        return out

    # ---------------------------------------------------------------- reflect (the briefing)
    def briefing_prompt(self, ticket: dict) -> tuple[str, str]:
        a, s, t = ticket["asset"], ticket["site"], ticket["tech"]
        query = (
            f"Brief {t.get('name', 'the technician')} ({t.get('role', '')}, {t.get('years', '?')} years experience) before they "
            f"attend work order {ticket['wo_id']} on {a['id']} ({a.get('model')}, serial {a.get('serial')}, installed {a.get('installed')}) "
            f"at {s.get('name')}. Alarm {ticket.get('alarm_code') or 'none'}. Symptom: {ticket['symptom']} "
            "What should they check first, what is most likely wrong, what must they NOT waste time on, which past advice is now "
            "obsolete because the equipment changed since, which parts should they carry, what site rules apply and who should they call if stuck?"
        )
        context = (
            f"Asset description: {a.get('desc')}. Site: {s.get('name')}, {s.get('locality')}; FM {s.get('facility_manager')}. "
            f"Priority {ticket.get('priority')}. Reported by {ticket.get('reported_by')}. Today is {ticket['opened_at'][:10]}."
        )
        return query, context

    async def briefing(self, ticket: dict, bank_id: str | None = None) -> dict:
        query, context = self.briefing_prompt(ticket)
        resp = to_dict(await self.client.areflect(
            bank_id or self.fleet, query, context=context, budget=settings.reflect_budget,
            response_schema=BRIEFING_SCHEMA, include_facts=True, max_tokens=3000,
        )) or {}
        structured = resp.get("structured_output") or {}
        based_on = resp.get("based_on") or {}
        memories = based_on.get("memories") or []
        return {
            "bank": bank_id or self.fleet,
            "text": resp.get("text", ""),
            "briefing": structured,
            "structured_error": resp.get("structured_output_error"),
            "evidence": [
                {"id": m.get("id"), "type": m.get("type"), "text": m.get("text"), "when": m.get("occurred_start") or m.get("mentioned_at"),
                 "document_id": m.get("document_id"), "wo_ids": sorted(set(WO_RE.findall((m.get("text") or "") + " " + (m.get("document_id") or ""))))}
                for m in memories
            ],
            "mental_models": [{"id": m.get("id"), "name": m.get("name")} for m in based_on.get("mental_models") or []],
            "directives": [d.get("name") for d in based_on.get("directives") or []],
            "usage": resp.get("usage"),
        }

    # ---------------------------------------------------------------- knowledge + stats
    async def mental_models(self, bank_id: str | None = None) -> list[dict]:
        return items_of(await self.client.alist_mental_models(bank_id or self.fleet, detail="content"))

    async def refresh_mental_model(self, mid: str, bank_id: str | None = None) -> Any:
        return to_dict(await self.client.arefresh_mental_model(bank_id or self.fleet, mid))

    async def stats(self, bank_id: str | None = None) -> dict:
        try:
            return to_dict(await self.client.banks.get_agent_stats(bank_id or self.fleet)) or {}
        except Exception as e:
            log.warning("stats unavailable: %s", e)
            return {}

    async def observations(self, bank_id: str | None = None, limit: int = 40) -> list[dict]:
        return items_of(await self.client.alist_memories(bank_id or self.fleet, type="observation", limit=limit))
