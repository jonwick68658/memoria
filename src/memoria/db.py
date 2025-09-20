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

import json
import logging
import uuid
from pathlib import Path
from typing import Any, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from .config import settings, MemoriaConfig

import alembic.config
import alembic.command

logger = logging.getLogger("memoria.db")
logger.setLevel(settings.log_level)


class DB:
    def __init__(self, engine):
        self.engine = engine
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    @classmethod
    def create(cls, config: Optional[MemoriaConfig] = None) -> "DB":
        """Factory that also runs migrations and registers pgvector adapter."""
        config = config or MemoriaConfig.from_env()
        engine = create_engine(config.database_url, echo=settings.debug)
        db = cls(engine)
        db.run_migrations()
        return db

    # ---------- migrations ----------
    def run_migrations(self) -> None:
        alembic_cfg = alembic.config.Config("db/alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", self.engine.url)
        alembic.command.upgrade(alembic_cfg, "head")

    # ---------- upserts / ensure ----------
    def ensure_user(self, user_id: str) -> None:
        with self.SessionLocal() as session:
            session.execute(text("INSERT INTO users(id) VALUES (:user_id) ON CONFLICT DO NOTHING"), {"user_id": user_id})
            session.commit()

    def ensure_conversation(self, user_id: str, conversation_id: str) -> None:
        self.ensure_user(user_id)
        with self.SessionLocal() as session:
            session.execute(
                text("INSERT INTO conversations(id, user_id) VALUES (:conversation_id, :user_id) ON CONFLICT DO NOTHING"),
                {"conversation_id": conversation_id, "user_id": user_id},
            )
            session.commit()

    # ---------- messages ----------
    def add_message(self, conversation_id: str, role: str, text: str, message_id: Optional[str] = None) -> str:
        mid = message_id or f"msg-{uuid.uuid4().hex}"
        with self.SessionLocal() as session:
            session.execute(
                text("INSERT INTO messages(id, conversation_id, role, content) VALUES (:mid, :conversation_id, :role, :text)"),
                {"mid": mid, "conversation_id": conversation_id, "role": role, "text": text},
            )
            session.commit()
        return mid

    def get_recent_messages(self, conversation_id: str, limit: int) -> List[dict[str, Any]]:
        with self.SessionLocal() as session:
            result = session.execute(
                text("SELECT id, role, content, created_at FROM messages WHERE conversation_id=:conversation_id ORDER BY created_at DESC LIMIT :limit"),
                {"conversation_id": conversation_id, "limit": limit},
            )
            rows = result.fetchall()
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
        mid = memory_id or f"mem-{uuid.uuid4().hex}"
        idem_key = idempotency_key or f"idem:{uuid.uuid5(uuid.NAMESPACE_DNS, text.lower()).hex}"
        with self.SessionLocal() as session:
            result = session.execute(
                text("""
                    INSERT INTO memories(id, user_id, conversation_id, content, embedding, type, importance, confidence, pinned, bad, idempotency_key, metadata)
                    VALUES (:mid, :user_id, :conversation_id, :text, :embedding::vector, :type, :importance, :confidence, :pinned, :bad, :idem_key, :prov::jsonb)
                    ON CONFLICT (user_id, idempotency_key) DO UPDATE SET updated_at=now()
                    RETURNING id
                """),
                {
                    "mid": mid,
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "text": text,
                    "embedding": embedding,
                    "type": type_,
                    "importance": importance,
                    "confidence": confidence,
                    "pinned": pinned,
                    "bad": bad,
                    "idem_key": idem_key,
                    "prov": json.dumps(prov),
                },
            )
            inserted_id = result.fetchone()[0]
            session.commit()
        return inserted_id

    def mark_memory_bad(self, user_id: str, memory_id: str) -> None:
        with self.SessionLocal() as session:
            session.execute(
                text("UPDATE memories SET bad=TRUE, updated_at=now() WHERE id=:memory_id AND user_id=:user_id"),
                {"memory_id": memory_id, "user_id": user_id},
            )
            session.commit()

    def get_recent_memories(self, user_id: str, conversation_id: Optional[str], limit: int) -> List[dict[str, Any]]:
        with self.SessionLocal() as session:
            if conversation_id:
                result = session.execute(
                    text("""
                        SELECT id, content, importance, confidence, created_at
                        FROM memories
                        WHERE user_id=:user_id AND (conversation_id=:conversation_id OR pinned=TRUE) AND bad=FALSE
                        ORDER BY created_at DESC
                        LIMIT :limit
                    """),
                    {"user_id": user_id, "conversation_id": conversation_id, "limit": limit},
                )
            else:
                result = session.execute(
                    text("""
                        SELECT id, content, importance, confidence, created_at
                        FROM memories
                        WHERE user_id=:user_id AND bad=FALSE
                        ORDER BY created_at DESC
                        LIMIT :limit
                    """),
                    {"user_id": user_id, "limit": limit},
                )
            rows = result.fetchall()
        return [{"id": r[0], "text": r[1], "importance": r[2], "confidence": r[3], "created_at": r[4]} for r in rows]

    # ---------- vector retrieval ----------
    def vector_search(self, user_id: str, query_emb: List[float], top_k: int, conversation_id: Optional[str]) -> List[dict[str, Any]]:
        with self.SessionLocal() as session:
            if conversation_id:
                result = session.execute(
                    text("""
                        SELECT id, content, GREATEST(0, 1 - (embedding <=> :query_emb::vector)) AS score
                        FROM memories
                        WHERE user_id=:user_id AND bad=FALSE AND (conversation_id=:conversation_id OR pinned=TRUE)
                        ORDER BY embedding <=> :query_emb::vector
                        LIMIT :top_k
                    """),
                    {"user_id": user_id, "query_emb": query_emb, "conversation_id": conversation_id, "top_k": top_k},
                )
            else:
                result = session.execute(
                    text("""
                        SELECT id, content, GREATEST(0, 1 - (embedding <=> :query_emb::vector)) AS score
                        FROM memories
                        WHERE user_id=:user_id AND bad=FALSE
                        ORDER BY embedding <=> :query_emb::vector
                        LIMIT :top_k
                    """),
                    {"user_id": user_id, "query_emb": query_emb, "top_k": top_k},
                )
            rows = result.fetchall()
        return [{"id": r[0], "text": r[1], "score": float(r[2])} for r in rows]

    # ---------- lexical retrieval ----------
    def lexical_search(self, user_id: str, query: str, top_k: int, conversation_id: Optional[str]) -> List[dict[str, Any]]:
        with self.SessionLocal() as session:
            if conversation_id:
                result = session.execute(
                    text("""
                        SELECT id, content, ts_rank(to_tsvector('english', content), plainto_tsquery('english', :query)) AS score
                        FROM memories
                        WHERE user_id=:user_id AND bad=FALSE AND (conversation_id=:conversation_id OR pinned=TRUE)
                          AND to_tsvector('english', content) @@ plainto_tsquery('english', :query)
                        ORDER BY score DESC
                        LIMIT :top_k
                    """),
                    {"user_id": user_id, "query": query, "conversation_id": conversation_id, "top_k": top_k},
                )
            else:
                result = session.execute(
                    text("""
                        SELECT id, content, ts_rank(to_tsvector('english', content), plainto_tsquery('english', :query)) AS score
                        FROM memories
                        WHERE user_id=:user_id AND bad=FALSE
                          AND to_tsvector('english', content) @@ plainto_tsquery('english', :query)
                        ORDER BY score DESC
                        LIMIT :top_k
                    """),
                    {"user_id": user_id, "query": query, "top_k": top_k},
                )
            rows = result.fetchall()
        return [{"id": r[0], "text": r[1], "score": float(r[2])} for r in rows]

    # ---------- summaries ----------
    def get_summary(self, user_id: str, conversation_id: str) -> Optional[dict[str, Any]]:
        with self.SessionLocal() as session:
            result = session.execute(
                text("SELECT id, content, citations, updated_at FROM summaries WHERE user_id=:user_id AND conversation_id=:conversation_id AND scope='rolling' LIMIT 1"),
                {"user_id": user_id, "conversation_id": conversation_id},
            )
            row = result.fetchone()
        if not row:
            return None
        return {"id": row[0], "content": row[1], "citations": row[2], "updated_at": row[3]}

    def upsert_summary(self, user_id: str, conversation_id: str, content: str, citations: List[str]) -> str:
        sid = f"sum-{user_id}-{conversation_id}"
        with self.SessionLocal() as session:
            session.execute(
                text("""
                    INSERT INTO summaries(id, user_id, conversation_id, scope, content, citations)
                    VALUES (:sid, :user_id, :conversation_id, 'rolling', :content, :citations::jsonb)
                    ON CONFLICT (id) DO UPDATE SET content=EXCLUDED.content, citations=EXCLUDED.citations, updated_at=now()
                """),
                {"sid": sid, "user_id": user_id, "conversation_id": conversation_id, "content": content, "citations": json.dumps(citations)},
            )
            session.commit()
        return sid

    # ---------- insights ----------
    def insert_insight(self, user_id: str, content: str) -> str:
        iid = f"ins-{uuid.uuid4().hex}"
        with self.SessionLocal() as session:
            session.execute(
                text("INSERT INTO insights(id, user_id, content) VALUES (:iid, :user_id, :content)"),
                {"iid": iid, "user_id": user_id, "content": content},
            )
            session.commit()
        return iid

    def get_insights(self, user_id: str, limit: int = 5) -> List[dict[str, Any]]:
        with self.SessionLocal() as session:
            result = session.execute(
                text("SELECT id, content, created_at FROM insights WHERE user_id=:user_id ORDER BY created_at DESC LIMIT :limit"),
                {"user_id": user_id, "limit": limit},
            )
            rows = result.fetchall()
        return [{"id": r[0], "content": r[1], "created_at": r[2]} for r in rows]

    def get_memories(self, user_id: str, conversation_id: Optional[str] = None, limit: int = 100) -> List[dict[str, Any]]:
        """Get memories for a user, optionally filtered by conversation."""
        return self.get_recent_memories(user_id, conversation_id, limit)