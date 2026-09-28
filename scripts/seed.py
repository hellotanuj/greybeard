"""Seed Hindsight with 18 months of fleet history.

    python scripts/seed.py            # configure banks, retain history, build fleet knowledge
    python scripts/seed.py --reset    # delete both banks first
    python scripts/seed.py --until 2025-09-01   # only retain history before a date (learning-curve demos)

Creates two banks with identical configuration:
  greybeard-fleet  <- all history
  greybeard-day1   <- nothing (the honest "Day 1" baseline)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from greybeard.catalog import Catalog  # noqa: E402
from greybeard.config import settings  # noqa: E402
from greybeard.memory import FleetMemory  # noqa: E402

BATCH = 20


async def wait_for_ingest(mem: FleetMemory, bank: str, timeout_s: int = 1800) -> None:
    start = time.time()
    while time.time() - start < timeout_s:
        s = await mem.stats(bank)
        pending = (s.get("pending_operations") or 0) + (s.get("pending_consolidation") or 0)
        print(f"  [{int(time.time() - start):4d}s] nodes={s.get('total_nodes')} observations={s.get('total_observations')} "
              f"docs={s.get('total_documents')} pending_ops={s.get('pending_operations')} pending_consolidation={s.get('pending_consolidation')}",
              flush=True)
        if s and pending == 0:
            return
        await asyncio.sleep(10)
    print("  timed out waiting; ingestion continues server-side")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="delete all Greybeard banks before seeding")
    ap.add_argument("--until", help="only retain work orders opened before this ISO date")
    ap.add_argument("--no-wait", action="store_true")
    ap.add_argument("--snapshots", action="store_true", help="also seed the Jun-2025 / Dec-2025 'memory as of' banks for the learning curve")
    args = ap.parse_args()

    catalog = Catalog()
    mem = FleetMemory()
    history = json.loads((ROOT / "data" / "history.json").read_text())
    if args.until:
        history = [j for j in history if j["opened_at"] < args.until]

    if args.reset:
        for bank in [h["bank"] for h in settings.horizons]:
            try:
                await mem.client.adelete_bank(bank)
                print(f"deleted {bank}")
            except Exception as e:
                print(f"(skip delete {bank}: {type(e).__name__})")

    print(f"configuring banks {mem.fleet} + {mem.day1}")
    for bank in (mem.fleet, mem.day1):
        await mem.configure_bank(bank)

    print("retaining site & technician profiles")
    await mem.retain_site_knowledge(catalog)

    print(f"retaining {len(history)} work orders in batches of {BATCH}")
    for i in range(0, len(history), BATCH):
        chunk = history[i:i + BATCH]
        await mem.retain_jobs(chunk, catalog, retain_async=True)
        print(f"  queued {i + len(chunk)}/{len(history)}  ({chunk[0]['opened_at'][:10]} .. {chunk[-1]['opened_at'][:10]})", flush=True)

    if args.snapshots:
        for h in settings.horizons:
            if h["key"] in ("day1", "fleet"):
                continue
            subset = [j for j in history if j["opened_at"] < h["until"]]
            print(f"snapshot bank {h['bank']}: {len(subset)} work orders before {h['until']}")
            await mem.configure_bank(h["bank"])
            await mem.retain_site_knowledge(catalog, bank_id=h["bank"])
            for i in range(0, len(subset), BATCH):
                await mem.retain_jobs(subset[i:i + BATCH], catalog, bank_id=h["bank"], retain_async=True)

    if not args.no_wait:
        print("waiting for extraction + consolidation into observations...")
        await wait_for_ingest(mem, mem.fleet)

    print("creating fleet knowledge pages (mental models)")
    for bank in (mem.fleet, mem.day1):
        await mem.ensure_mental_models(bank)
    for m in await mem.mental_models(mem.fleet):
        try:
            await mem.refresh_mental_model(m["id"])
        except Exception as e:
            print(f"  refresh {m.get('id')} skipped: {e}")
    print("done. start the app with: make run")


if __name__ == "__main__":
    asyncio.run(main())
