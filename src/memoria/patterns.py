from __future__ import annotations

from .db import DB
from .llm import LLMGateway

INSIGHT_SYSTEM = "You are an analyst. You find helpful, non-obvious patterns and recommendations for the user."
INSIGHT_PROMPT = """You are given a list of the user’s stored memory snippets (facts, preferences, plans, entities).
Your job is to:
- Identify themes and patterns across their interests, projects, or recurring constraints.
- Suggest concrete next steps or niche directions that align with those patterns.
- Cite memory IDs you rely on using [[mem-...]] form when you reference a specific snippet.

Memories:
{mems}

Write a concise insights report (250-400 words) with actionable recommendations.
"""

def generate_insights(
    db: DB,
    llm: LLMGateway,
    user_id: str,
    conversation_id: str | None = None,
    limit: int = 50,
) -> str:
    mems = db.get_recent_memories(user_id, conversation_id, limit=limit)
    text_blob = "\n".join(f"- [{m['id']}] {m['text']}" for m in mems)
    content = llm.chat(
        INSIGHT_SYSTEM, INSIGHT_PROMPT.format(mems=text_blob), max_tokens=600, temperature=0.2
    )
    db.insert_insight(user_id, content)
    return content