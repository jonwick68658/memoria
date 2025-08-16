from __future__ import annotations

import re
from typing import Any, List

from .config import settings
from .db import DB
from .llm import LLMGateway

SUM_SYSTEM = "You produce concise rolling summaries with citations. Be faithful; do not invent."
SUM_PROMPT = """Update the summary for this.

Rules:
- Keep it under {max_tokens} tokens.
- Include only facts you can ground in the provided messages or existing summary.
- Prefer durable facts and decisions over small talk.
- If you use any Fact IDs embedded like [[mem-...]], keep them in the summary for provenance.

Existing summary (may be empty):
{existing}

Recent messages (chronological):
{messages}

Write the updated summary now.
"""

def update_rolling_summary(
    db: DB,
    llm: LLMGateway,
    user_id: str,
    conversation_id: str,
    recent_messages: List[dict[str, Any]],
) -> str:
    existing = db.get_summary(user_id, conversation_id)
    existing_text = existing["content"] if existing else ""

    msgs = "\n".join(f"{m['role']}: {m['text']}" for m in recent_messages)
    prompt = SUM_PROMPT.format(
        max_tokens=settings.summary_max_tokens,
        existing=existing_text,
        messages=msgs,
    )
    content = llm.chat(SUM_SYSTEM, prompt, max_tokens=settings.summary_max_tokens, temperature=0.0)
    citations = re.findall(r"\[\[(.*?)\]\]", content)
    db.upsert_summary(user_id, conversation_id, content, citations)
    return content