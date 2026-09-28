"""In-memory stand-in for the Hindsight client, used by the test suite.

It records every call so tests can assert *how* Greybeard uses memory (tags,
document ids, timestamps, schemas) without needing network access.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any


class FakeHindsight:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.retained: dict[str, list[dict]] = {}
        self.directives: dict[str, list[dict]] = {}
        self.models: dict[str, list[dict]] = {}
        self.banks = SimpleNamespace(get_agent_stats=self._stats)

    async def _stats(self, bank_id: str) -> dict:
        items = self.retained.get(bank_id, [])
        return {"bank_id": bank_id, "total_nodes": len(items) * 3, "total_documents": len({i.get("document_id") for i in items}),
                "total_observations": len(items) // 4, "pending_operations": 0, "pending_consolidation": 0}

    async def acreate_bank(self, bank_id: str, **kw: Any) -> dict:
        self.calls.append(("create_bank", {"bank_id": bank_id, **kw}))
        return {"bank_id": bank_id}

    async def aupdate_bank_config(self, bank_id: str, **kw: Any) -> dict:
        self.calls.append(("update_bank_config", {"bank_id": bank_id, **kw}))
        return {}

    async def alist_directives(self, bank_id: str, **kw: Any) -> dict:
        return {"items": self.directives.get(bank_id, [])}

    async def acreate_directive(self, bank_id: str, **kw: Any) -> dict:
        self.directives.setdefault(bank_id, []).append(kw)
        return kw

    async def aretain_batch(self, bank_id: str, items: list[dict], **kw: Any) -> dict:
        self.calls.append(("retain_batch", {"bank_id": bank_id, "items": items, **kw}))
        self.retained.setdefault(bank_id, []).extend(items)
        return {"success": True, "bank_id": bank_id, "items_count": len(items), "async": kw.get("retain_async", False)}

    async def arecall(self, bank_id: str, query: str, **kw: Any) -> dict:
        self.calls.append(("recall", {"bank_id": bank_id, "query": query, **kw}))
        wanted = set(kw.get("tags") or [])
        hits = [i for i in self.retained.get(bank_id, []) if not wanted or wanted & set(i.get("tags", []))]
        return {"results": [{"id": str(n), "text": h["content"], "type": "experience", "document_id": h.get("document_id"), "tags": h.get("tags")}
                            for n, h in enumerate(hits[:8])]}

    async def areflect(self, bank_id: str, query: str, **kw: Any) -> dict:
        self.calls.append(("reflect", {"bank_id": bank_id, "query": query, **kw}))
        mems = self.retained.get(bank_id, [])
        if not mems:
            return {"text": "I have no history for this asset.", "structured_output": {
                "headline": "No history on record; follow standard OEM troubleshooting.", "confidence": "low",
                "check_first": [{"step": "Follow OEM alarm troubleshooting chart", "why": "No prior jobs in memory"}], "likely_causes": []}}
        return {
            "text": "Check fan bank 2 drive parameter P-212 first.",
            "structured_output": {
                "headline": "Bank 2 drive was factory-reset on WO-2609-038; Quiet Mode P-212 is probably back on.",
                "confidence": "high",
                "check_first": [{"step": "Check P-212 on fan bank 2 SD-40 drive", "why": "Factory reset re-enables Quiet Mode", "minutes": 10, "evidence": ["WO-2608-041", "WO-2609-038"]}],
                "likely_causes": [{"cause": "Quiet Mode capping fan speed", "likelihood": 80, "evidence": ["WO-2608-041"]}],
                "superseded": [{"old_advice": "Replace VFD panel fan", "why_obsolete": "Drives replaced by sealed SD-40 in Aug 2026", "evidence": ["WO-2505-012", "WO-2608-041"]}],
                "avoid": [{"action": "Coil wash", "why": "Failed twice in 2025", "evidence": ["WO-2504-058"]}],
            },
            "based_on": {"memories": [{"id": "m1", "type": "observation", "text": "SD-40 drives ship with P-212 enabled (WO-2608-041)", "document_id": "WO-2608-041"}],
                         "mental_models": [{"id": "failure-patterns", "name": "Recurring failure patterns"}], "directives": [{"name": "cite-evidence"}]},
        }

    async def alist_mental_models(self, bank_id: str, **kw: Any) -> dict:
        return {"items": self.models.get(bank_id, [])}

    async def acreate_mental_model(self, bank_id: str, **kw: Any) -> dict:
        self.models.setdefault(bank_id, []).append({"id": kw["id"], "name": kw["name"], "content": None, **kw})
        return {"operation_id": "op"}

    async def arefresh_mental_model(self, bank_id: str, mid: str) -> dict:
        return {"operation_id": "op"}

    async def alist_memories(self, bank_id: str, **kw: Any) -> dict:
        return {"items": []}

    async def adelete_bank(self, bank_id: str) -> None:
        self.retained.pop(bank_id, None)
