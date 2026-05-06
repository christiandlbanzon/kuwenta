"""LLM provider routing.

Picks the configured provider per purpose. Providers are lazy-initialized and cached.
Fallback chain on transient errors is the caller's responsibility (see services/qa.py
and services/insights.py for examples).
"""

from typing import Literal, cast

from app.config import ProviderName, get_settings
from app.llm.base import LLMProvider

Purpose = Literal["categorization", "qa", "ocr", "insights", "parse_quickadd", "anomaly_explain"]

_CACHE: dict[ProviderName, LLMProvider] = {}


def _build_provider(name: ProviderName) -> LLMProvider:
    if name == "gemini":
        from app.llm.providers.gemini import GeminiProvider

        return cast(LLMProvider, GeminiProvider())
    if name == "groq":
        from app.llm.providers.groq import GroqProvider

        return cast(LLMProvider, GroqProvider())
    if name == "ollama":
        from app.llm.providers.ollama import OllamaProvider

        return cast(LLMProvider, OllamaProvider())
    raise ValueError(f"Unknown provider: {name}")


def get_provider(name: ProviderName) -> LLMProvider:
    if name not in _CACHE:
        _CACHE[name] = _build_provider(name)
    return _CACHE[name]


def get_provider_for_purpose(purpose: Purpose) -> LLMProvider:
    settings = get_settings()
    mapping: dict[Purpose, ProviderName] = {
        "categorization": settings.llm_provider_categorization,
        "qa": settings.llm_provider_qa,
        "ocr": settings.llm_provider_ocr,
        "insights": settings.llm_provider_insights,
        "parse_quickadd": settings.llm_provider_categorization,
        "anomaly_explain": settings.llm_provider_insights,
    }
    return get_provider(mapping[purpose])


def reset_cache() -> None:
    """Test-only: clear the provider cache."""
    _CACHE.clear()
