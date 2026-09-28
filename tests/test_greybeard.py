import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "tests"))

from fake_hindsight import FakeHindsight  # noqa: E402
from greybeard import main  # noqa: E402
from greybeard.catalog import catalog  # noqa: E402
from greybeard.memory import BRIEFING_SCHEMA, FleetMemory, job_to_item, render_job, tags_for  # noqa: E402

HISTORY = json.loads((ROOT / "data" / "history.json").read_text())


@pytest.fixture()
def fake(monkeypatch):
    fh = FakeHindsight()
    monkeypatch.setattr(main, "memory", FleetMemory(client=fh))
    catalog.reset()
    yield fh
    catalog.reset()


@pytest.fixture()
def client(fake):
    return TestClient(main.app)


# ------------------------------------------------------------------ data quality
def test_history_is_chronological_and_unique():
    ids = [j["wo_id"] for j in HISTORY]
    assert len(ids) == len(set(ids))
    assert [j["opened_at"] for j in HISTORY] == sorted(j["opened_at"] for j in HISTORY)


def test_every_job_references_known_asset_and_tech():
    for j in HISTORY:
        assert j["asset_id"] in catalog.assets, j["wo_id"]
        assert j["technician"] in catalog.techs, j["wo_id"]


def test_story_encodes_failed_fixes_and_supersedence():
    outcomes = {j["wo_id"]: j["outcome"] for j in HISTORY}
    assert outcomes["WO-2504-058"] == "not_fixed"          # coil wash that didn't work
    assert outcomes["WO-2505-012"] == "fixed"              # the real fix
    retrofit = next(j for j in HISTORY if j["wo_id"] == "WO-2608-041")
    assert "NO LONGER APPLY" in retrofit["notes"]          # later knowledge overrides earlier


# ------------------------------------------------------------------ memory shaping
def test_tags_cover_asset_model_site_outcome():
    job = next(j for j in HISTORY if j["wo_id"] == "WO-2505-012")
    tags = tags_for(job, catalog.assets[job["asset_id"]])
    assert {"asset:ORB-CH-02", "site:orbit", "type:chiller", "model:kryo-acx-500", "outcome:fixed", "tech:ravi"} <= set(tags)


def test_rendered_job_preserves_ids_for_citation():
    job = next(j for j in HISTORY if j["wo_id"] == "WO-2507-071")
    a = catalog.assets[job["asset_id"]]
    text = render_job(job, a, catalog.sites[a["site"]], catalog.techs[job["technician"]])
    assert "WO-2507-071" in text and "LAK-CH-01" in text and "KX-1908-0233" in text
    assert "false alarm" in text.lower()


def test_retain_item_uses_event_time_and_document_id():
    job = HISTORY[10]
    item = job_to_item(job, catalog)
    assert item["document_id"] == job["wo_id"]
    assert item["timestamp"].isoformat().startswith(job["closed_at"][:13])


def test_briefing_schema_requires_core_fields():
    assert {"headline", "confidence", "check_first", "likely_causes"} <= set(BRIEFING_SCHEMA["required"])
    assert "superseded" in BRIEFING_SCHEMA["properties"]


# ------------------------------------------------------------------ API
def test_tickets_are_enriched(client):
    r = client.get("/api/tickets").json()
    assert len(r) == 5 and r[0]["asset"]["model"] and r[0]["site"]["name"]


def test_briefing_uses_reflect_with_schema_and_selected_bank(client, fake):
    fake.retained["greybeard-fleet"] = [job_to_item(HISTORY[0], catalog)]
    r = client.post("/api/tickets/WO-2609-114/briefing?bank=fleet").json()
    call = [c for c in fake.calls if c[0] == "reflect"][-1][1]
    assert call["bank_id"] == "greybeard-fleet"
    assert call["response_schema"] == BRIEFING_SCHEMA and call["include_facts"] is True
    assert r["briefing"]["superseded"] and r["evidence"][0]["wo_ids"] == ["WO-2608-041"]


def test_day1_horizon_hits_empty_bank(client, fake):
    r = client.post("/api/tickets/WO-2609-114/briefing?bank=day1").json()
    assert r["bank"] == "greybeard-day1" and r["briefing"]["confidence"] == "low"


def test_recall_uses_strict_asset_scope_then_fleet(client, fake):
    client.get("/api/tickets/WO-2609-114/recall")
    recalls = [c[1] for c in fake.calls if c[0] == "recall"]
    assert recalls[0]["tags"] == ["asset:ORB-CH-02"] and recalls[0]["tags_match"] == "any_strict"
    assert "model:kryo-acx-500" in recalls[1]["tags"]


def test_closeout_retains_job_and_feedback(client, fake):
    body = {"outcome": "fixed", "root_cause": "P-212 re-enabled after reset", "notes": "Disabled P-212 on bank 2 drive, discharge normal.",
            "parts": [], "downtime_hours": 1.5, "briefing_helpful": True, "briefing_feedback": "spot on"}
    r = client.post("/api/tickets/WO-2609-114/close", json=body)
    assert r.status_code == 200 and r.json()["retained"] == 2
    items = [i for c in fake.calls if c[0] == "retain_batch" for i in c[1]["items"]]
    assert items[0]["document_id"] == "WO-2609-114" and "outcome:fixed" in items[0]["tags"]
    assert "kind:briefing-feedback" in items[1]["tags"]
    assert client.post("/api/tickets/WO-2609-114/close", json=body).status_code == 409


def test_closeout_validation(client):
    r = client.post("/api/tickets/WO-2609-114/close", json={"outcome": "maybe", "root_cause": "x", "notes": "short"})
    assert r.status_code == 422


def test_unknown_ticket_404(client):
    assert client.get("/api/tickets/WO-0000-000").status_code == 404


@pytest.mark.asyncio
async def test_configure_bank_is_idempotent_for_directives():
    fh = FakeHindsight()
    mem = FleetMemory(client=fh)
    await mem.configure_bank("b")
    await mem.configure_bank("b")
    names = [d["name"] for d in fh.directives["b"]]
    assert len(names) == len(set(names)) == 4


def test_fleet_timeline_includes_same_model_units_and_live_closeouts(client):
    r = client.get("/api/fleet/timeline?asset_id=HLX-CH-04").json()
    assert r["assets"][0] == "HLX-CH-04" and "ORB-CH-02" in r["assets"]
    assert not [j for j in r["jobs"] if j["asset_id"] == "HLX-CH-04"]   # brand-new unit: no history
    body = {"outcome": "fixed", "root_cause": "P-212 factory default", "notes": "Disabled P-212 on all four drives.", "downtime_hours": 0}
    client.post("/api/tickets/WO-2609-133/close", json=body)
    r = client.get("/api/fleet/timeline?asset_id=HLX-CH-04").json()
    assert [j for j in r["jobs"] if j["wo_id"] == "WO-2609-133"]


def test_bootstrap_seeds_once_then_refuses(client, fake, monkeypatch):
    from dataclasses import replace
    monkeypatch.setattr(main, "settings", replace(main.settings, hindsight_api_key="hsk_test"))
    r = client.post("/api/bootstrap?snapshots=true")
    assert r.status_code == 200, r.text
    q = r.json()["queued"]
    assert q["greybeard-fleet"] == len(HISTORY) and q["greybeard-fleet-2025-06"] < q["greybeard-fleet-2025-12"] < len(HISTORY)
    assert "greybeard-day1" not in fake.retained                    # Day-1 bank stays empty on purpose
    assert {m["id"] for m in fake.models["greybeard-fleet"]} == {"failure-patterns", "failed-fixes", "site-playbook", "expertise-map"}
    assert client.post("/api/bootstrap").status_code == 409          # can't be re-run to spam retains


def test_public_bootstrap_disabled(client, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    assert client.post("/api/bootstrap").status_code == 403


def test_service_errors_do_not_expose_credentials():
    error = main._hindsight_error(RuntimeError("secret-key-sentinel"))
    assert "secret-key-sentinel" not in error.detail
