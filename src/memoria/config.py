from __future__ import annotations

import os
from typing import Optional, List
from pydantic import BaseModel, Field, ValidationError


class MemoriaConfig(BaseModel):
    """Configuration for a Memoria instance."""
    
    # Database configuration
    database_url: str = Field(default="postgresql://postgres:postgres@localhost:5432/memoria", 
                            description="Database connection URL")
    
    # LLM provider configuration
    providers: List[str] = Field(default_factory=lambda: ["openai", "openrouter"],
                               description="LLM providers in priority order")
    
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    openrouter_api_key: Optional[str] = Field(default=None, description="OpenRouter API key")
    openrouter_site_url: Optional[str] = Field(default=None, description="OpenRouter site URL")
    openrouter_app_name: Optional[str] = Field(default=None, description="OpenRouter app name")
    
    # Model configuration
    llm_model: str = Field(default="gpt-4o-mini", description="LLM model to use")
    embedding_model: str = Field(default="text-embedding-3-small", description="Embedding model to use")
    
    # Memory and retrieval settings
    retrieval_top_k: int = Field(default=16, description="Number of memories to retrieve")
    history_limit: int = Field(default=12, description="Number of recent messages to include")
    memory_limit: int = Field(default=24, description="Number of recent memories to include")
    summary_max_tokens: int = Field(default=800, description="Maximum tokens for summaries")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    
    # Timeout settings
    connect_timeout: float = Field(default=10.0, description="Connection timeout in seconds")
    read_timeout: float = Field(default=60.0, description="Read timeout in seconds")
    write_timeout: float = Field(default=10.0, description="Write timeout in seconds")
    total_timeout: float = Field(default=90.0, description="Total timeout in seconds")
    
    # Async processing (optional)
    enable_async: bool = Field(default=False, description="Enable async processing with Celery")
    redis_url: Optional[str] = Field(default=None, description="Redis URL for async processing")
    
    @classmethod
    def from_env(cls) -> "MemoriaConfig":
        """Create configuration from environment variables."""
        return cls(
            database_url=os.getenv("MEMORIA_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/memoria"),
            providers=[p.strip() for p in os.getenv("MEMORIA_PROVIDERS", "openai,openrouter").split(",") if p.strip()],
            openai_api_key=os.getenv("MEMORIA_OPENAI_API_KEY"),
            openrouter_api_key=os.getenv("MEMORIA_OPENROUTER_API_KEY"),
            openrouter_site_url=os.getenv("MEMORIA_OPENROUTER_SITE_URL"),
            openrouter_app_name=os.getenv("MEMORIA_OPENROUTER_APP_NAME"),
            llm_model=os.getenv("MEMORIA_LLM_MODEL", "gpt-4o-mini"),
            embedding_model=os.getenv("MEMORIA_EMBEDDING_MODEL", "text-embedding-3-small"),
            retrieval_top_k=int(os.getenv("MEMORIA_RETRIEVAL_TOP_K", "16")),
            history_limit=int(os.getenv("MEMORIA_HISTORY_LIMIT", "12")),
            memory_limit=int(os.getenv("MEMORIA_MEMORY_LIMIT", "24")),
            summary_max_tokens=int(os.getenv("MEMORIA_SUMMARY_MAX_TOKENS", "800")),
            log_level=os.getenv("MEMORIA_LOG_LEVEL", "INFO"),
            connect_timeout=float(os.getenv("MEMORIA_CONNECT_TIMEOUT", "10")),
            read_timeout=float(os.getenv("MEMORIA_READ_TIMEOUT", "60")),
            write_timeout=float(os.getenv("MEMORIA_WRITE_TIMEOUT", "10")),
            total_timeout=float(os.getenv("MEMORIA_TOTAL_TIMEOUT", "90")),
            enable_async=os.getenv("MEMORIA_ENABLE_ASYNC", "false").lower() == "true",
            redis_url=os.getenv("MEMORIA_REDIS_URL"),
        )


# Legacy global settings for backward compatibility (to be deprecated)
class LegacySettings(BaseModel):
    gateway_api_key: str = Field(default_factory=lambda: os.getenv("GATEWAY_API_KEY", "change-me"))
    database_url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/memoria"))
    providers: List[str] = Field(default_factory=lambda: [p.strip() for p in os.getenv("PROVIDERS", "openai,openrouter").split(",") if p.strip()])
    openai_api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openrouter_api_key: str = Field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    openrouter_site_url: str = Field(default_factory=lambda: os.getenv("OPENROUTER_SITE_URL", ""))
    openrouter_app_name: str = Field(default_factory=lambda: os.getenv("OPENROUTER_APP_NAME", ""))
    llm_model: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))
    embedding_model: str = Field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
    retrieval_top_k: int = Field(default_factory=lambda: int(os.getenv("RETRIEVAL_TOP_K", "16")))
    history_limit: int = Field(default_factory=lambda: int(os.getenv("HISTORY_LIMIT", "12")))
    memory_limit: int = Field(default_factory=lambda: int(os.getenv("MEMORY_LIMIT", "24")))
    summary_max_tokens: int = Field(default_factory=lambda: int(os.getenv("SUMMARY_MAX_TOKENS", "800")))
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    connect_timeout: float = Field(default_factory=lambda: float(os.getenv("CONNECT_TIMEOUT", "10")))
    read_timeout: float = Field(default_factory=lambda: float(os.getenv("READ_TIMEOUT", "60")))
    write_timeout: float = Field(default_factory=lambda: float(os.getenv("WRITE_TIMEOUT", "10")))
    total_timeout: float = Field(default_factory=lambda: float(os.getenv("TOTAL_TIMEOUT", "90")))
    rate_limit_rps: float = Field(default_factory=lambda: float(os.getenv("RATE_LIMIT_RPS", "0")))

settings = LegacySettings()

def validate_settings() -> None:
    available = []
    for p in settings.providers:
        if p == "openai" and settings.openai_api_key:
            available.append(p)
        elif p == "openrouter" and settings.openrouter_api_key:
            available.append(p)
    if not available:
        raise RuntimeError("No usable providers configured. Set at least one of OPENAI_API_KEY or OPENROUTER_API_KEY and PROVIDERS.")