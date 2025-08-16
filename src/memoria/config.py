import os
from pydantic import BaseModel, Field, ValidationError

class Settings(BaseModel):
    gateway_api_key: str = Field(default_factory=lambda: os.getenv("GATEWAY_API_KEY", "change-me"))
    database_url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/memoria"))

    # Providers in priority order, with fallback (e.g., "openai,openrouter")
    providers: list[str] = Field(default_factory=lambda: [p.strip() for p in os.getenv("PROVIDERS", "openai,openrouter").split(",") if p.strip()])

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

    # HTTP/LLM client timeouts
    connect_timeout: float = Field(default_factory=lambda: float(os.getenv("CONNECT_TIMEOUT", "10")))
    read_timeout: float = Field(default_factory=lambda: float(os.getenv("READ_TIMEOUT", "60")))
    write_timeout: float = Field(default_factory=lambda: float(os.getenv("WRITE_TIMEOUT", "10")))
    total_timeout: float = Field(default_factory=lambda: float(os.getenv("TOTAL_TIMEOUT", "90")))

    # Simple in-process rate limit (requests per second per API key); 0 disables
    rate_limit_rps: float = Field(default_factory=lambda: float(os.getenv("RATE_LIMIT_RPS", "0")))

settings = Settings()

def validate_settings() -> None:
    # Fail fast if no provider is usable
    available = []
    for p in settings.providers:
        if p == "openai" and settings.openai_api_key:
            available.append(p)
        elif p == "openrouter" and settings.openrouter_api_key:
            available.append(p)
    if not available:
        raise RuntimeError("No usable providers configured. Set at least one of OPENAI_API_KEY or OPENROUTER_API_KEY and PROVIDERS.")