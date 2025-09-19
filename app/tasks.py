from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from celery import current_task
from app.celery_app import celery
from src.memoria.sdk import MemoriaClient
from src.memoria.llm import EmbeddingClient

logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=3)
def process_memory_async(
    self, user_id: str, conversation_id: str, message_content: str, metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Async chat processing using MemoriaClient.

    This mirrors the synchronous chat flow:
    - ensures conversation
    - stores user message
    - extracts/writes memories (with security)
    - builds context and calls LLM
    - stores assistant message
    - updates rolling summary (best-effort)
    """
    try:
        logger.info("Processing async chat user_id=%s conv_id=%s", user_id, conversation_id)

        client = MemoriaClient.create()
        resp = client.chat(user_id=user_id, conversation_id=conversation_id, question=message_content)

        result: Dict[str, Any] = {
            "status": "success",
            "assistant_text": resp.assistant_text,
            "cited_ids": resp.cited_ids,
            "assistant_message_id": resp.assistant_message_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        logger.info("Async chat completed user_id=%s conv_id=%s msg_id=%s", user_id, conversation_id, resp.assistant_message_id)
        return result

    except Exception as exc:
        logger.exception("process_memory_async failed user_id=%s conv_id=%s: %s", user_id, conversation_id, exc)
        # Exponential backoff: 60s, 120s, 240s
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)


@celery.task(bind=True, max_retries=3)
def correct_memory_async(self, user_id: str, memory_id: str, replacement_text: str) -> Dict[str, Any]:
    """Mark memory as bad and write a corrected replacement."""
    try:
        logger.info("Correcting memory user_id=%s memory_id=%s", user_id, memory_id)
        client = MemoriaClient.create()
        client.correct(user_id=user_id, memory_id=memory_id, replacement_text=replacement_text)

        return {
            "status": "success",
            "user_id": user_id,
            "original_memory_id": memory_id,
            "replacement_preview": (replacement_text[:100] + "...") if len(replacement_text) > 100 else replacement_text,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        logger.exception("correct_memory_async failed user_id=%s memory_id=%s: %s", user_id, memory_id, exc)
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)


@celery.task(bind=True, max_retries=2)
def batch_process_embeddings(self, memory_batch: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate embeddings for a batch of memory payloads.

    memory_batch: list of dicts with keys:
      - id: memory id (string)
      - content: text to embed (string)
    """
    try:
        logger.info("Batch embedding started count=%d", len(memory_batch))
        embedding_client = EmbeddingClient()
        results: List[Dict[str, Any]] = []

        for item in memory_batch:
            text = str(item.get("content", ""))
            mid = str(item.get("id", ""))
            emb = embedding_client.embed(text)
            results.append({"memory_id": mid, "embedding": emb})

        return {
            "status": "success",
            "processed": len(results),
            "results": results,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        logger.exception("batch_process_embeddings failed: %s", exc)
        raise self.retry(exc=exc, countdown=120)


@celery.task(bind=True, max_retries=3)
def generate_insights_async(self, user_id: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
    """Generate insights asynchronously for a user (optionally scoped to a conversation)."""
    try:
        logger.info("Generating insights async user_id=%s conv_id=%s", user_id, conversation_id)
        client = MemoriaClient.create()
        insights = client.generate_insights(user_id=user_id, conversation_id=conversation_id)

        return {
            "status": "success",
            "user_id": user_id,
            "conversation_id": conversation_id,
            "insights_count": len(insights),
            "insights": insights,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        logger.exception("generate_insights_async failed user_id=%s conv_id=%s: %s", user_id, conversation_id, exc)
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)


@celery.task(bind=True)
def update_user_summary_async(self, user_id: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
    """Placeholder: summaries are updated inline with chat. This task is a no-op for compatibility."""
    logger.info("update_user_summary_async noop user_id=%s conv_id=%s", user_id, conversation_id)
    return {
        "status": "success",
        "message": "Summary is updated during chat; no-op task executed.",
        "user_id": user_id,
        "conversation_id": conversation_id,
        "timestamp": datetime.utcnow().isoformat(),
    }