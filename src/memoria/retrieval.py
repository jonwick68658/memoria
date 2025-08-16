from __future__ import annotations

from typing import Any, Dict

from .config import settings
from .db import DB
from .llm import EmbeddingClient


def build_context(
    db: DB,
    user_id: str,
    conversation_id: str,
    question: str,
    *,
    top_k: int | None = None,
    history_limit: int | None = None,
    memory_limit: int | None = None,
) -> Dict[str, Any]:
    top_k = top_k or settings.retrieval_top_k
    history_limit = history_limit or settings.history_limit
    memory_limit = memory_limit or settings.memory_limit

    # Recent messages
    msgs = db.get_recent_messages(conversation_id, history_limit)

    # Rolling summary
    summary = db.get_summary(user_id, conversation_id)

    # Embedding of the current user query
    q_emb = EmbeddingClient().embed(question)

    # Vector + lexical retrieval
    vec = db.vector_search(user_id, q_emb, top_k=top_k, conversation_id=conversation_id)
    lex = db.lexical_search(user_id, question, top_k=top_k, conversation_id=conversation_id)

    # Recent raw memories
    recent = db.get_recent_memories(user_id, conversation_id, limit=memory_limit)

    # Merge & score (simple weighted fusion + recency tie-break)
    by_id: dict[str, dict[str, Any]] = {}
    for m in vec:
        by_id.setdefault(m["id"], {"id": m["id"], "text": m["text"], "v": 0.0, "l": 0.0, "rec": None})
        by_id[m["id"]]["v"] = max(by_id[m["id"]]["v"], m["score"])
    for m in lex:
        by_id.setdefault(m["id"], {"id": m["id"], "text": m["text"], "v": 0.0, "l": 0.0, "rec": None})
        by_id[m["id"]]["l"] = max(by_id[m["id"]]["l"], m["score"])
    for rank, m in enumerate(recent):
        by_id.setdefault(m["id"], {"id": m["id"], "text": m["text"], "v": 0.0, "l": 0.0, "rec": rank})
        if by_id[m["id"]]["rec"] is None:
            by_id[m["id"]]["rec"] = rank
        else:
            by_id[m["id"]]["rec"] = min(by_id[m["id"]]["rec"], rank)

    items = []
    for m in by_id.values():
        base = 0.6 * m.get("v", 0.0) + 0.4 * m.get("l", 0.0)
        rec_rank = m.get("rec", 9999) or 9999
        items.append((m["id"], m["text"], base, rec_rank))
    items.sort(key=lambda x: (-(x[2]), x[3]))
    top_items = items[:memory_limit]

    facts = [{"id": mid, "text": text} for (mid, text, *_rest) in top_items]

    return {
        "messages": list(reversed(msgs)),  # chronological
        "summary": summary["content"] if summary else None,
        "facts": facts,
    }