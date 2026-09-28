"""Static reference data (sites, assets, technicians) and the live dispatch board.

Reference data is the "CMMS" side of the product: the asset register a facility
services company already has. Memory (what actually happened, what worked, what
didn't) lives in Hindsight, not here.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from .config import settings


class Catalog:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or settings.data_dir
        self._lock = threading.Lock()
        self.sites: dict[str, dict] = {s["id"]: s for s in self._load("sites.json")}
        self.assets: dict[str, dict] = {a["id"]: a for a in self._load("assets.json")}
        self.techs: dict[str, dict] = {t["id"]: t for t in self._load("technicians.json")}
        # Serverless filesystems (Vercel) are read-only except the temp dir.
        state_dir = Path(tempfile.gettempdir()) if os.getenv("VERCEL") else self.data_dir
        self._state_path = state_dir / "greybeard_runtime_state.json"
        self._tickets: list[dict] = self._load_state()

    # ------------------------------------------------------------------ io
    def _load(self, name: str) -> Any:
        return json.loads((self.data_dir / name).read_text())

    def _load_state(self) -> list[dict]:
        if self._state_path.exists():
            return json.loads(self._state_path.read_text())["tickets"]
        return [dict(t, status="open") for t in self._load("open_tickets.json")]

    def _save_state(self) -> None:
        self._state_path.write_text(json.dumps({"tickets": self._tickets}, indent=2))

    def reset(self) -> None:
        with self._lock:
            if self._state_path.exists():
                self._state_path.unlink()
            self._tickets = self._load_state()

    # ------------------------------------------------------------------ queries
    def tickets(self) -> list[dict]:
        return [self.enrich(t) for t in self._tickets]

    def ticket(self, wo_id: str) -> dict | None:
        for t in self._tickets:
            if t["wo_id"] == wo_id:
                return self.enrich(t)
        return None

    def enrich(self, ticket: dict) -> dict:
        asset = self.assets.get(ticket["asset_id"], {})
        site = self.sites.get(asset.get("site", ""), {})
        tech = self.techs.get(ticket.get("technician", ""), {})
        return {**ticket, "asset": asset, "site": site, "tech": tech}

    def close_ticket(self, wo_id: str, closeout: dict) -> dict | None:
        with self._lock:
            for t in self._tickets:
                if t["wo_id"] == wo_id:
                    t["status"] = "closed"
                    t["closeout"] = closeout
                    self._save_state()
                    return self.enrich(t)
        return None


catalog = Catalog()
