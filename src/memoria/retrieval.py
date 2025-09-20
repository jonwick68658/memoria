# Copyright (C) 2025 neuroLM
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Any, Dict

from .config import settings
from .db import DB
from .llm import EmbeddingClient
import redis
import json
import hashlib
import logging

logger = logging.getLogger(__name__)
import redis
import json
import hashlib


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

    # Redis client for caching
    r = redis.from_url(settings.redis_url)

    # Cache key for retrieval results
    cache_key = f"retrieval:{user_id}:{conversation_id}:{hashlib.md5(question.encode()).hexdigest()}"

    # Try to get cached results
    cached = r.get(cache_key)
    if cached:
        logger.info("Cache hit for retrieval")
        vec, lex = json.loads(cached)
    else:
        # Recent messages and summary (always fresh)
        msgs = db.get_recent_messages(conversation_id, history_limit)
        summary = db.get_summary(user_id, conversation_id)
    
        # Embedding of the current user query
        q_emb = EmbeddingClient().embed(question)
    
        # Redis client for caching
        r = redis.from_url(settings.redis_url)
    
        # Cache key for retrieval results
        cache_key = f"retrieval:{user_id}:{conversation_id}:{hashlib.md5(question.encode()).hexdigest()}"
    
        # Try to get cached results
        cached = r.get(cache_key)
        if cached:
            logger.info("Cache hit for retrieval")
            vec, lex = json.loads(cached)
        else:
            # Vector + lexical retrieval
            vec = db.vector_search(user_id, q_emb, top_k=top_k, conversation_id=conversation_id)
            lex = db.lexical_search(user_id, question, top_k=top_k, conversation_id=conversation_id)
    
            # Cache the results
            r.setex(cache_key, 3600, json.dumps([vec, lex]))  # TTL 1h
            logger.info("Cached retrieval results")

        # Cache the results
        r.setex(cache_key, 3600, json.dumps([vec, lex]))  # TTL 1h
        logger.info("Cached retrieval results")

    # Recent raw memories (not cached, as they change)
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