from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, Field

from .config import settings
from .db import DB
from .llm import LLMGateway, EmbeddingClient
from .retrieval import build_context
from .writer import maybe_write_memories
from .summarizer import update_rolling_summary
from .patterns import generate_insights


class AssistantResponse(BaseModel):
    assistant_text: str
    cited_ids: list[str] = Field(default_factory=list)
    assistant_message_id: str | None = None


@dataclass
class MemoriaClient:
    db: DB
    llm: LLMGateway

    @classmethod
    def create(cls) -> "MemoriaClient":
        return cls(db=DB.create(), llm=LLMGateway())

    def chat(self, user_id: str, conversation_id: str, question: str) -> AssistantResponse:
        # Ensure conversation exists
        self.db.ensure_conversation(user_id, conversation_id)

        # Persist user turn
        self.db.add_message(conversation_id, role="user", text=question)

        # Extract durable memories
        maybe_write_memories(self.db, self.llm, user_id, conversation_id, question)

        # Build context
        ctx = build_context(self.db, user_id, conversation_id, question)

        # Compose prompts
        messages_block = "\n".join(f"{m['role']}: {m['text']}" for m in ctx["messages"])
        summary_block = ctx["summary"] or ""
        facts_block = "\n".join(f"- [{f['id']}] {f['text']}" for f in ctx["facts"])

        system_prompt = (
            "You are a helpful assistant.\n"
            "Use the Facts to personalize any user-specific claims and include the memory ID in double brackets like [[mem-...]] after such claims.\n"
            "For general knowledge or domain questions, answer normally using your knowledge.\n"
            "Never invent user-specific facts that are not present in Facts. If a personal detail is missing, ask a brief clarifying question.\n"
            "Be concise and actionable."
        )

        user_prompt = f"""Conversation summary (may be empty)
{summary_block}

Prior messages (chronological)
{messages_block}

Facts (for personalization only)
{facts_block}

User question
{question}

Assistant:"""

        answer = self.llm.chat(system_prompt, user_prompt, max_tokens=900, temperature=0.2)

        # Pull cited memory ids from the answer
        cited_ids = re.findall(r"\[\[(.*?)\]\]", answer)

        # Persist assistant turn
        msg_id = self.db.add_message(conversation_id, role="assistant", text=answer)

        # Update rolling summary (best-effort)
        try:
            update_rolling_summary(
                self.db,
                self.llm,
                user_id,
                conversation_id,
                recent_messages=ctx["messages"] + [{"role": "assistant", "text": answer}],
            )
        except Exception:
            pass

        return AssistantResponse(assistant_text=answer, cited_ids=cited_ids, assistant_message_id=msg_id)

    def correct(self, user_id: str, memory_id: str, replacement_text: str) -> None:
        self.db.mark_memory_bad(user_id, memory_id)
        emb = EmbeddingClient().embed(replacement_text)
        self.db.add_memory(
            user_id=user_id,
            conversation_id=None,
            text=replacement_text,
            embedding=emb,
            type_="correction",
            importance=0.6,
            confidence=0.9,
            provenance={"source": "correction", "replaces": memory_id},
        )

    def generate_insights(self, user_id: str, conversation_id: str | None = None) -> str:
        return generate_insights(self.db, self.llm, user_id, conversation_id)