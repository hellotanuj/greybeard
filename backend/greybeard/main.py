"""Greybeard HTTP API + static frontend."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .baseline import llm_baseline
from .catalog import catalog
from .config import settings
from .memory import FleetMemory, to_dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("greybeard")

app = FastAPI(title="Greybeard", version="1.0.0", description="Field-service memory agent built on Hindsight")
memory = FleetMemory()


class CloseOut(BaseModel):
    outcome: str = Field(pattern="^(fixed|not_fixed|false_alarm)$")
    root_cause: str = Field(min_length=3, max_length=400)
    notes: str = Field(min_length=10, max_length=4000)
    parts: list[str] = []
    downtime_hours: float = Field(default=0, ge=0, le=720)
    briefing_helpful: bool | None = None
    briefing_feedback: str | None = Field(default=None, max_length=1000)


class Ask(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


def _ticket(wo_id: str) -> dict:
    t = catalog.ticket(wo_id)
    if not t:
        raise HTTPException(404, f"Unknown work order {wo_id}")
    return t


def _hindsight_error(e: Exception) -> HTTPException:
    log.exception("Hindsight call failed")
    return HTTPException(502, "The memory service could not complete this request. Please try again shortly.")


# ----------------------------------------------------------------------------- read models
@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "hindsight": settings.hindsight_base_url, "fleet_bank": memory.fleet, "day1_bank": memory.day1,
            "baseline": "llm" if settings.has_llm else "day1-bank", "has_key": bool(settings.hindsight_api_key)}


@app.get("/api/horizons")
async def horizons() -> list[dict]:
    return settings.horizons


@app.get("/api/tickets")
async def tickets() -> list[dict]:
    return catalog.tickets()


@app.get("/api/tickets/{wo_id}")
async def ticket(wo_id: str) -> dict:
    return _ticket(wo_id)


@app.get("/api/assets/{asset_id}/history")
async def asset_history(asset_id: str) -> list[dict]:
    """Raw CMMS log for the asset: what a technician would otherwise scroll through."""
    history = json.loads((settings.data_dir / "history.json").read_text())
    return [j for j in history if j["asset_id"] == asset_id][::-1]


@app.get("/api/fleet/timeline")
async def fleet_timeline(asset_id: str) -> dict:
    """Every job on this asset and on every other unit of the same model (for the memory timeline)."""
    asset = catalog.assets.get(asset_id)
    if not asset:
        raise HTTPException(404, f"Unknown asset {asset_id}")
    siblings = [a["id"] for a in catalog.assets.values() if a["model"] == asset["model"] or a["id"] == asset_id]
    siblings.sort(key=lambda x: (x != asset_id, x))
    history = json.loads((settings.data_dir / "history.json").read_text())
    jobs = [{k: j[k] for k in ("wo_id", "asset_id", "opened_at", "outcome", "symptom", "root_cause", "technician", "alarm_code")}
            for j in history if j["asset_id"] in siblings]
    for t in catalog.tickets():  # jobs closed live in the UI are part of memory too
        if t.get("status") == "closed" and t["asset_id"] in siblings:
            c = t["closeout"]
            jobs.append({"wo_id": t["wo_id"], "asset_id": t["asset_id"], "opened_at": c["closed_at"], "outcome": c["outcome"],
                         "symptom": t["symptom"], "root_cause": c["root_cause"], "technician": t.get("technician"), "alarm_code": t.get("alarm_code")})
    return {"assets": siblings, "jobs": jobs, "horizons": settings.horizons}


# ----------------------------------------------------------------------------- memory-powered
@app.post("/api/tickets/{wo_id}/briefing")
async def briefing(wo_id: str, bank: str = "fleet") -> dict:
    t = _ticket(wo_id)
    try:
        res = await memory.briefing(t, settings.bank_for(bank))
        res["horizon"] = bank
        return res
    except Exception as e:
        raise _hindsight_error(e)


@app.post("/api/tickets/{wo_id}/baseline")
async def baseline(wo_id: str) -> dict:
    t = _ticket(wo_id)
    prompt, context = memory.briefing_prompt(t)
    generic = await llm_baseline(prompt, context)
    if generic is not None:
        return {"source": f"stateless LLM ({settings.llm_model})", "briefing": generic, "evidence": []}
    try:
        res = await memory.briefing(t, memory.day1)
        res["source"] = "Day-1 memory bank (same config, no history)"
        return res
    except Exception as e:
        raise _hindsight_error(e)


@app.get("/api/tickets/{wo_id}/recall")
async def recall(wo_id: str) -> dict:
    t = _ticket(wo_id)
    try:
        return await memory.recall_for_ticket(t)
    except Exception as e:
        raise _hindsight_error(e)


@app.post("/api/tickets/{wo_id}/close")
async def close(wo_id: str, body: CloseOut) -> dict:
    """The learning loop: the technician's close-out becomes memory immediately."""
    t = _ticket(wo_id)
    if t.get("status") == "closed":
        raise HTTPException(409, "Work order already closed")
    now = datetime.now().replace(microsecond=0)
    job = {
        "wo_id": wo_id, "asset_id": t["asset_id"], "site": t["asset"].get("site"),
        "opened_at": t["opened_at"], "closed_at": now.isoformat(), "technician": t.get("technician"),
        "alarm_code": t.get("alarm_code"), "symptom": t["symptom"], "notes": body.notes, "root_cause": body.root_cause,
        "outcome": body.outcome, "parts": body.parts, "downtime_hours": body.downtime_hours, "kind": "corrective",
    }
    jobs = [job]
    try:
        await memory.retain_jobs(jobs, catalog, retain_async=True)
        if body.briefing_helpful is not None:
            # The agent also learns about its own advice: was the briefing right?
            verdict = "was correct and saved time" if body.briefing_helpful else "was WRONG or unhelpful"
            fb = {
                "content": (f"Feedback on Greybeard's pre-job briefing for {wo_id} on {t['asset_id']}: the briefing {verdict}. "
                            f"Actual root cause: {body.root_cause}. Technician comment: {body.briefing_feedback or 'none'}"),
                "timestamp": now, "context": "technician feedback on agent briefing", "document_id": f"{wo_id}-feedback",
                "tags": [f"asset:{t['asset_id']}", "kind:briefing-feedback", f"tech:{t.get('technician')}"],
            }
            await memory.client.aretain_batch(memory.fleet, items=[fb], retain_async=True)
    except Exception as e:
        raise _hindsight_error(e)
    closed = catalog.close_ticket(wo_id, {**body.model_dump(), "closed_at": now.isoformat()})
    return {"ok": True, "ticket": closed, "retained": len(jobs) + (1 if body.briefing_helpful is not None else 0)}


@app.post("/api/ask")
async def ask(body: Ask) -> dict:
    try:
        resp = to_dict(await memory.client.areflect(memory.fleet, body.question, budget="mid", include_facts=True)) or {}
    except Exception as e:
        raise _hindsight_error(e)
    mems = ((resp.get("based_on") or {}).get("memories") or [])
    return {"answer": resp.get("text", ""), "evidence": [{"type": m.get("type"), "text": m.get("text"), "document_id": m.get("document_id")} for m in mems][:12]}


@app.get("/api/knowledge")
async def knowledge() -> list[dict]:
    try:
        return await memory.mental_models()
    except Exception as e:
        raise _hindsight_error(e)


@app.post("/api/knowledge/{mid}/refresh")
async def refresh_knowledge(mid: str) -> dict:
    try:
        return {"ok": True, "result": await memory.refresh_mental_model(mid)}
    except Exception as e:
        raise _hindsight_error(e)


@app.get("/api/observations")
async def observations() -> list[dict]:
    try:
        return await memory.observations()
    except Exception as e:
        raise _hindsight_error(e)


@app.get("/api/stats")
async def stats() -> dict:
    return {"fleet": await memory.stats(memory.fleet), "day1": await memory.stats(memory.day1)}


@app.get("/api/bootstrap/status")
async def bootstrap_status() -> dict:
    s = await memory.stats(memory.fleet)
    return {"configured": bool(settings.hindsight_api_key), "documents": s.get("total_documents", 0) or 0,
            "pending": (s.get("pending_operations") or 0) + (s.get("pending_consolidation") or 0) + ((s.get("operations_by_status") or {}).get("processing") or 0),
            "observations": s.get("total_observations", 0) or 0, "reachable": bool(s), "setup_allowed": not bool(os.getenv("VERCEL"))}


@app.post("/api/bootstrap")
async def bootstrap(snapshots: bool = True) -> dict:
    """Seed Hindsight with the fleet history from the server itself (used on Vercel).

    Only allowed while the fleet bank is empty, so it can't be used to spam retains.
    Retains are queued async; Hindsight extracts and consolidates in the background.
    """
    if os.getenv("VERCEL"):
        raise HTTPException(403, "Fleet setup is managed by the owner.")
    if not settings.hindsight_api_key:
        raise HTTPException(400, "The memory service is not connected yet.")
    s = await memory.stats(memory.fleet)
    if (s.get("total_documents") or 0) > 0:
        raise HTTPException(409, "Fleet memory is already seeded")
    history = json.loads((settings.data_dir / "history.json").read_text())
    try:
        queued = await seed_banks(history, snapshots=snapshots)
    except Exception as e:
        raise _hindsight_error(e)
    return {"ok": True, **queued}


async def seed_banks(history: list[dict], snapshots: bool = True, batch: int = 20) -> dict:
    counts = {}
    for bank in (memory.fleet, memory.day1):
        await memory.configure_bank(bank)
    await memory.retain_site_knowledge(catalog)
    for i in range(0, len(history), batch):
        await memory.retain_jobs(history[i:i + batch], catalog, retain_async=True)
    counts[memory.fleet] = len(history)
    if snapshots:
        for h in settings.horizons:
            if h["key"] in ("day1", "fleet"):
                continue
            subset = [j for j in history if j["opened_at"] < h["until"]]
            await memory.configure_bank(h["bank"])
            await memory.retain_site_knowledge(catalog, bank_id=h["bank"])
            for i in range(0, len(subset), batch):
                await memory.retain_jobs(subset[i:i + batch], catalog, bank_id=h["bank"], retain_async=True)
            counts[h["bank"]] = len(subset)
    for bank in (memory.fleet, memory.day1):
        await memory.ensure_mental_models(bank)  # refresh_after_consolidation keeps them current
    return {"queued": counts}


@app.post("/api/demo/reset")
async def reset() -> dict:
    catalog.reset()
    return {"ok": True}


# ----------------------------------------------------------------------------- frontend
app.mount("/static", StaticFiles(directory=settings.frontend_dir), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(settings.frontend_dir / "index.html")
