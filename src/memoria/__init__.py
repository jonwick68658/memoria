"""
Memoria - AI Memory SDK for LLM applications
"""

from .config import MemoriaConfig, settings, validate_settings
from .db import DB
from .llm import LLMGateway, EmbeddingClient
from .sdk import MemoriaClient, AssistantResponse
from .retrieval import build_context
from .writer import maybe_write_memories
from .summarizer import update_rolling_summary
from .patterns import generate_insights

__version__ = "0.1.0"

__all__ = [
    "MemoriaClient",
    "AssistantResponse",
    "MemoriaConfig",
    "settings",
    "validate_settings",
    "DB",
    "LLMGateway",
    "EmbeddingClient",
    "build_context",
    "maybe_write_memories",
    "update_rolling_summary",
    "generate_insights",
]