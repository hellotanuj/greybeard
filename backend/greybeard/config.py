"""Runtime configuration, loaded from environment / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    hindsight_base_url: str = field(default_factory=lambda: os.getenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io"))
    hindsight_api_key: str | None = field(default_factory=lambda: os.getenv("HINDSIGHT_API_KEY") or None)

    # The veteran brain: 18 months of fleet history lives here.
    fleet_bank: str = field(default_factory=lambda: os.getenv("GREYBEARD_FLEET_BANK", "greybeard-fleet"))
    # Same configuration, zero history. Used for the honest "Day 1" comparison.
    day1_bank: str = field(default_factory=lambda: os.getenv("GREYBEARD_DAY1_BANK", "greybeard-day1"))

    # Optional OpenAI-compatible LLM (Groq, xAI, OpenAI...). Only used for the
    # "no memory" baseline column; everything memory-backed goes through Hindsight reflect.
    llm_base_url: str | None = field(default_factory=lambda: os.getenv("LLM_BASE_URL") or None)
    llm_api_key: str | None = field(default_factory=lambda: os.getenv("LLM_API_KEY") or None)
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "openai/gpt-oss-120b"))

    reflect_budget: str = field(default_factory=lambda: os.getenv("GREYBEARD_REFLECT_BUDGET", "mid"))
    data_dir: Path = ROOT / "data"
    frontend_dir: Path = ROOT / "frontend"

    @property
    def horizons(self) -> list[dict]:
        """Memory 'as of' snapshots used for the learning-curve view.

        Each is a real bank seeded only with work orders opened before `until`.
        """
        return [
            {"key": "day1", "label": "Day 1", "bank": self.day1_bank, "until": "0000"},
            {"key": "2025-06", "label": "Jun 2025", "bank": f"{self.fleet_bank}-2025-06", "until": "2025-07-01"},
            {"key": "2025-12", "label": "Dec 2025", "bank": f"{self.fleet_bank}-2025-12", "until": "2026-01-01"},
            {"key": "fleet", "label": "Today", "bank": self.fleet_bank, "until": None},
        ]

    def bank_for(self, key: str | None) -> str:
        for h in self.horizons:
            if h["key"] == key:
                return h["bank"]
        return self.fleet_bank

    @property
    def has_llm(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key)


settings = Settings()
