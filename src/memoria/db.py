from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any, List, Optional

import psycopg
from psycopg.pool import ConnectionPool
from pgvector.psycopg import register_vector

from .config import settings, MemoriaConfig

logger = logging.getLogger("memoria.db")
logger.setLevel(settings.log_level)


class DB:
    def __init__(self, pool: ConnectionPool):
        self.pool = pool

    @classmethod
    def create(cls, config: Optional[MemoriaConfig] = None) -> "DB":
        """Factory that also runs migrations and registers pgvector adapter."""
        config = config or MemoriaConfig.from_env()
        
        def configure(conn: psycopg.Connection) -> None:
            conn.autocommit = True
            register_vector(conn)

        pool = ConnectionPool(conninfo=config.database_url, configure=configure, kwargs={"autocommit": True})
        db = cls(pool)
        db.run_migrations()
        return db

    # ---------- migrations ----------
    def run_migrations(self) -> None:
        # Use relative path for migrations from the package directory
        migrations_dir = Path(__file__).parent.parent.parent / "db" / "migrations"
        if not migrations_dir.exists():
            logger.warning("Migrations dir not found: %s", migrations_dir)
            return
        with self.pool.connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())")
            applied = {r[0] for r in conn.execute("SELECT version FROM schema_migrations").fetchall()}
            for path in sorted(migrations_dir.glob("*.sql")):
                version = path.stem
                if version in applied:
                    continue
                sql = path.read_text(encoding="utf-8")
                logger.info("Applying migration %s", version)
                conn.execute(sql)
                conn.execute("INSERT INTO schema_migrations(version) VALUES (%s)", (version,))

    # ---------- upserts / ensure ----------
    def ensure_user(self, user_id: str) -> None:
        with self.pool.connection() as conn:
            conn.execute("INSERT INTO users(id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))

    def ensure_conversation(self, user_id: str, conversation_id: str) -> None:
        self.ensure_user(user_id)
        with self.pool.connection() as conn:
            conn.execute(
                "INSERT INTO conversations(id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (conversation_id, user_id),
            )

    # ---------- messages ----------
    def add_message(self, conversation_id: str, role: str, text: str, message_id: Optional[str] = None) -> str:
        mid = message_id or f"msg-{uuid.uuid4().hex}"
        with self.pool.connection() as conn:
            conn.execute(
                "INSERT INTO messages(id, conversation_id, role, text) VALUES (%s,%s,%s,%s)",
                (mid, conversation_id, role, text),
            )
        return mid

    def get_recent_messages(self, conversation_id: str, limit: int) -> List[dict[str, Any]]:
        with self.pool.connection() as conn:
            cur = conn.execute(
                "SELECT id, role, text, created_at FROM messages WHERE conversation_id=%s ORDER BY created_at DESC LIMIT %s",
                (conversation_id, limit),
            )
            rows = cur.fetchall()
        return [{"id": r[0], "role": r[1], "text": r[2], "created_at": r[3]} for r in rows]

    # ---------- memories ----------
    def add_memory(
        self,
        user_id: str,
        conversation_id: Optional[str],
        text: str,
        embedding: List[float],
        *,
        type_: str = "fact",
        importance: float = 0.5,
        confidence: float = 0.8,
        pinned: bool = False,
        bad: bool = False,
        idempotency_key: str = "",
        provenance: Optional[dict[str, Any]] = None,
        memory_id: Optional[str] = None,
    ) -> str:
        prov = provenance or {}
        with self.pool.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO memories(id, user_id, conversation_id, type, text, embedding, importance, confidence, pinned, bad, idempotency_key, provenance)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (user_id, idempotency_key) DO UPDATE SET updated_at=now()
                RETURNING id
                """,
                (
                    memory_id or f"mem-{uuid.uuid4().hex}",
                    user_id,
                    conversation_id,
                    type_,
                    text,
                    embedding,  # pgvector adapter handles list -> vector
                    importance,
                    confidence,
                    pinned,
                    bad,
                    idempotency_key or f"idem:{uuid.uuid5(uuid.NAMESPACE_DNS, text.lower()).hex}",
                    json.dumps(prov),
                ),
            )
            inserted_id = cur.fetchone()[0]
        return inserted_id

    def mark_memory_bad(self, user_id: str, memory_id: str) -> None:
        with self.pool.connection() as conn:
            conn.execute("UPDATE memories SET bad=TRUE, updated_at=now() WHERE id=%s AND user_id=%s", (memory_id, user_id))

    def get_recent_memories(self, user_id: str, conversation_id: Optional[str], limit: int) -> List[dict[str, Any]]:
        with self.pool.connection() as conn:
            if conversation_id:
                cur = conn.execute(
                    """
                    SELECT id, text, importance, confidence, created_at
                    FROM memories
                    WHERE user_id=%s AND (conversation_id=%s OR pinned=TRUE) AND bad=FALSE
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (user_id, conversation_id, limit),
                )
            else:
                cur = conn.execute(
                    """
                    SELECT id, text, importance, confidence, created_at
                    FROM memories
                    WHERE user_id=%s AND bad=FALSE
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
            rows = cur.fetchall()
        return [{"id": r[0], "text": r[1], "importance": r[2], "confidence": r[3], "created_at": r[4]} for r in rows]

    # ---------- vector retrieval ----------
    def vector_search(self, user_id: str, query_emb: List[float], top_k: int, conversation_id: Optional[str]) -> List[dict[str, Any]]:
        with self.pool.connection() as conn:
            if conversation_id:
                cur = conn.execute(
                    """
                    SELECT id, text, GREATEST(0, 1 - (embedding <=> %s::vector)) AS score
                    FROM memories
                    WHERE user_id=%s AND bad=FALSE AND (conversation_id=%s OR pinned=TRUE)
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (query_emb, user_id, conversation_id, query_emb, top_k),
                )
            else:
                cur = conn.execute(
                    """
                    SELECT id, text, GREATEST(0, 1 - (embedding <=> %s::vector)) AS score
                    FROM memories
                    WHERE user_id=%s AND bad=FALSE
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (query_emb, user_id, query_emb, top_k),
                )
            rows = cur.fetchall()
        return [{"id": r[0], "text": r[1], "score": float(r[2])} for r in rows]

    # ---------- lexical retrieval ----------
    def lexical_search(self, user_id: str, query: str, top_k: int, conversation_id: Optional[str]) -> List[dict[str, Any]]:
        with self.pool.connection() as conn:
            if conversation_id:
                cur = conn.execute(
                    """
                    SELECT id, text, ts_rank(to_tsvector('english', text), plainto_tsquery('english', %s)) AS score
                    FROM memories
                    WHERE user_id=%s AND bad=FALSE AND (conversation_id=%s OR pinned=TRUE)
                      AND to_tsvector('english', text) @@ plainto_tsquery('english', %s)
                    ORDER BY score DESC
                    LIMIT %s
                    """,
                    (query, user_id, conversation_id, query, top_k),
                )
            else:
                cur = conn.execute(
                    """
                    SELECT id, text, ts_rank(to_tsvector('english', text), plainto_tsquery('english', %s)) AS score
                    FROM memories
                    WHERE user_id=%s AND bad=FALSE
                      AND to_tsvector('english', text) @@ plainto_tsquery('english', %s)
                    ORDER BY score DESC
                    LIMIT %s
                    """,
                    (query, user_id, query, top_k),
                )
            rows = cur.fetchall()
        return [{"id": r[0], "text": r[1], "score": float(r[2])} for r in rows]

    # ---------- summaries ----------
    def get_summary(self, user_id: str, conversation_id: str) -> Optional[dict[str, Any]]:
        with self.pool.connection() as conn:
            row = conn.execute(
                "SELECT id, content, citations, updated_at FROM summaries WHERE user_id=%s AND conversation_id=%s AND scope='rolling' LIMIT 1",
                (user_id, conversation_id),
            ).fetchone()
        if not row:
            return None
        return {"id": row[0], "content": row[1], "citations": row[2], "updated_at": row[3]}

    def upsert_summary(self, user_id: str, conversation_id: str, content: str, citations: List[str]) -> str:
        sid = f"sum-{user_id}-{conversation_id}"
        with self.pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO summaries(id, user_id, conversation_id, scope, content, citations)
                VALUES (%s,%s,%s,'rolling',%s,%s::jsonb)
                ON CONFLICT (id) DO UPDATE SET content=EXCLUDED.content, citations=EXCLUDED.citations, updated_at=now()
                """,
                (sid, user_id, conversation_id, content, json.dumps(citations)),
            )
        return sid

    # ---------- insights ----------
    def insert_insight(self, user_id: str, content: str) -> str:
        iid = f"ins-{uuid.uuid4().hex}"
        with self.pool.connection() as conn:
            conn.execute("INSERT INTO insights(id, user_id, content) VALUES (%s,%s,%s)", (iid, user_id, content))
        return iid

    def get_insights(self, user_id: str, limit: int = 5) -> List[dict[str, Any]]:
        with self.pool.connection() as conn:
            rows = conn.execute(
                "SELECT id, content, created_at FROM insights WHERE user_id=%s ORDER BY created_at DESC LIMIT %s",
                (user_id, limit),
            ).fetchall()
        return [{"id": r[0], "content": r[1], "created_at": r[2]} for r in rows]

    def get_memories(self, user_id: str, conversation_id: Optional[str] = None, limit: int = 100) -> List[dict[str, Any]]:
        """Get memories for a user, optionally filtered by conversation."""
        return self.get_recent_memories(user_id, conversation_id, limit)