"""The "no memory" baseline: what a stateless assistant tells the technician.

If an OpenAI-compatible LLM is configured (Groq, xAI, OpenAI...), we ask it the
exact same question with no memory at all. Otherwise we fall back to Hindsight
reflect against the empty Day-1 bank: identical configuration, zero history.
Either way, the comparison is honest: the only variable is memory.
"""

from __future__ import annotations

import json
import logging

import httpx

from .config import settings

log = logging.getLogger("greybeard.baseline")

SYSTEM = (
    "You are a field-service assistant for commercial HVAC, generator, lift and UPS equipment. "
    "Brief the technician before the job. Be concise. Return JSON with keys: headline (string), "
    "check_first (list of {step, why, minutes}), likely_causes (list of {cause, likelihood}), "
    "parts_to_carry (list of strings), site_notes (list of strings)."
)


async def llm_baseline(prompt: str, context: str) -> dict | None:
    if not settings.has_llm:
        return None
    body = {
        "model": settings.llm_model,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"{prompt}\n\nContext: {context}"}],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    try:
        async with httpx.AsyncClient(timeout=60) as http:
            r = await http.post(f"{settings.llm_base_url.rstrip('/')}/chat/completions", json=body,
                                headers={"Authorization": f"Bearer {settings.llm_api_key}"})
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:  # malformed JSON, tool-call errors, rate limits: degrade gracefully
        log.warning("LLM baseline failed, falling back to Day-1 bank: %s", e)
        return None
