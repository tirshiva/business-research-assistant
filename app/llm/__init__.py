"""LLM provider factory."""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.core.exceptions import LLMConfigurationError
from app.llm.base import LLMProvider
from app.llm.bedrock import BedrockLLMProvider
from app.llm.local import LocalLLMProvider


def create_llm_provider(
    provider_name: str | None = None,
    *,
    settings: object | None = None,
) -> LLMProvider:
    """Create an LLM provider from configuration."""
    cfg = settings or get_settings()
    name = (provider_name or getattr(cfg, "llm_provider", "local")).strip().lower()

    if name == "local":
        return LocalLLMProvider()
    if name == "bedrock":
        return BedrockLLMProvider(
            model_id=getattr(cfg, "bedrock_model_id", ""),
            region=getattr(cfg, "bedrock_region", ""),
            max_tokens=getattr(cfg, "llm_max_tokens", 2048),
            temperature=getattr(cfg, "llm_temperature", 0.0),
        )
    raise LLMConfigurationError(
        f"Unsupported LLM provider: {name}",
        provider=name,
    )


@lru_cache
def get_llm_provider() -> LLMProvider:
    """Return a process-wide LLM provider instance."""
    return create_llm_provider()
