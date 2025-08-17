from __future__ import annotations

import hashlib
import json
from typing import Any

from .db import DB
from .llm import LLMGateway, EmbeddingClient

EXTRACT_SYSTEM = "You are a precise extractor. Output JSON only."
EXTRACT_PROMPT = """From the user's latest message, extract durable, user-specific memories to store.
Only include: stable preferences, explicit corrections, facts about the user or their projects, decisions/plans with dates, or clear entities/relationships.
Do not include generic knowledge or assistant content.
Output a JSON array of objects: [
  {{"type": "preference|correction|fact|plan|entity|relation", "text": "...", "idempotency_key": "stable-key", "confidence": 0.0-1.0}}
]
If there are none, output [].

User message:
{msg}
"""

def _idem(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def maybe_write_memories(
    db: DB,
    llm: LLMGateway,
    user_id: str,
    conversation_id: str,
    user_text: str,
) -> list[str]:
    prompt = EXTRACT_PROMPT.format(msg=user_text)
    raw = llm.chat(EXTRACT_SYSTEM, prompt, max_tokens=500, temperature=0.0)
    try:
        items = json.loads(raw)
        if not isinstance(items, list):
            items = []
    except Exception:
        items = []

    mem_ids: list[str] = []
    for it in items:
        text = (it.get("text") or "").strip()
        type_ = (it.get("type") or "fact").strip()
        confidence = float(it.get("confidence", 0.8))
        if not text or confidence < 0.6:
            continue
        idem = it.get("idempotency_key") or _idem(f"{user_id}|{text.lower()}")
        emb = EmbeddingClient().embed(text)
        mid = db.add_memory(
            user_id=user_id,
            conversation_id=conversation_id,
            text=text,
            embedding=emb,
            type_=type_,
            importance=0.6 if type_ in ("preference", "plan") else 0.5,
            confidence=confidence,
            idempotency_key=idem,
            provenance={"source": "user_message"},
        )
        mem_ids.append(mid)
    return mem_ids