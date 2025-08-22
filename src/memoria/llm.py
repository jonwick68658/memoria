from __future__ import annotations

import logging
from typing import Dict, List, Optional

import httpx
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type

from .config import settings, MemoriaConfig

logger = logging.getLogger("memoria.llm")
logger.setLevel(settings.log_level)


def _normalize_model(provider: str, model: str) -> str:
    # For OpenRouter, accept plain OpenAI model names and normalize to openai/<model>
    if provider == "openrouter" and "/" not in model:
        return f"openai/{model}"
    return model


def _provider_headers(provider: str, config: MemoriaConfig) -> Dict[str, str]:
    if provider != "openrouter":
        return {}
    headers: Dict[str, str] = {}
    if config.openrouter_site_url:
        headers["HTTP-Referer"] = config.openrouter_site_url
    if config.openrouter_app_name:
        headers["X-Title"] = config.openrouter_app_name
    return headers


class _Backend:
    def __init__(self, provider: str, config: MemoriaConfig):
        self.provider = provider
        if provider == "openrouter":
            api_key = config.openrouter_api_key or ""
            base_url = "https://openrouter.ai/api/v1"
        else:
            provider = "openai"
            api_key = config.openai_api_key or ""
            base_url = None

        timeout = httpx.Timeout(
            timeout=config.total_timeout,
            connect=config.connect_timeout,
            read=config.read_timeout,
            write=config.write_timeout,
        )
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        self.extra_headers = _provider_headers(provider, config)

    def chat(self, model: str, system_prompt: str, user_prompt: str, *, max_tokens: int, temperature: float) -> str:
        model = _normalize_model(self.provider, model)
        resp = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            extra_headers=self.extra_headers or None,
        )
        return (resp.choices[0].message.content or "").strip()

    def embed(self, model: str, text: str) -> List[float]:
        model = _normalize_model(self.provider, model)
        resp = self.client.embeddings.create(
            model=model,
            input=[text],
            extra_headers=self.extra_headers or None,
        )
        return resp.data[0].embedding


class LLMGateway:
    def __init__(self, config: Optional[MemoriaConfig] = None):
        config = config or MemoriaConfig.from_env()
        self.config = config
        self.model = config.llm_model

        # Build backends for available providers in order
        self.backends: List[_Backend] = []
        for p in config.providers:
            if p == "openai" and config.openai_api_key:
                self.backends.append(_Backend("openai", config))
            elif p == "openrouter" and config.openrouter_api_key:
                self.backends.append(_Backend("openrouter", config))

        if not self.backends:
            raise RuntimeError("No usable LLM providers configured")

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.5, max=4.0),
        retry=retry_if_exception_type(Exception),
    )
    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> str:
        last_err = None
        for b in self.backends:
            try:
                return b.chat(settings.llm_model, system_prompt, user_prompt, max_tokens=max_tokens, temperature=temperature)
            except Exception as e:
                last_err = e
                logger.warning("Provider %s failed for chat; trying next. Error: %s", b.provider, e)
        assert last_err is not None
        raise last_err


class EmbeddingClient:
    def __init__(self, config: Optional[MemoriaConfig] = None):
        config = config or MemoriaConfig.from_env()
        self.config = config
        self.model = config.embedding_model
        self.backends: List[_Backend] = []
        for p in config.providers:
            if p == "openai" and config.openai_api_key:
                self.backends.append(_Backend("openai", config))
            elif p == "openrouter" and config.openrouter_api_key:
                self.backends.append(_Backend("openrouter", config))
        if not self.backends:
            raise RuntimeError("No usable embedding providers configured")

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.5, max=4.0),
        retry=retry_if_exception_type(Exception),
    )
    def embed(self, text: str) -> List[float]:
        last_err = None
        for b in self.backends:
            try:
                return b.embed(settings.embedding_model, text)
            except Exception as e:
                last_err = e
                logger.warning("Provider %s failed for embedding; trying next. Error: %s", b.provider, e)
        assert last_err is not None
        raise last_err