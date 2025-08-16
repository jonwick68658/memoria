from __future__ import annotations

from .llm import EmbeddingClient

# Thin facade for consistency with older imports
_embedding = EmbeddingClient()

def embed(text: str) -> list[float]:
    return _embedding.embed(text)