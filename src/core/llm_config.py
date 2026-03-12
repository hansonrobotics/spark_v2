"""Environment-driven configuration helpers for LLM providers."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _trim_trailing_slash(url: str) -> str:
    return url.rstrip("/")


def resolve_provider(provider: Optional[str] = None) -> str:
    if provider:
        return provider

    env_provider = os.getenv("LLM_PROVIDER")
    if env_provider:
        return env_provider.lower()

    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "openai"


def resolve_api_key(provider: Optional[str] = None) -> str:
    resolved_provider = resolve_provider(provider)
    if resolved_provider == "anthropic":
        return os.getenv("ANTHROPIC_API_KEY", os.getenv("LLM_API_KEY", ""))
    return os.getenv("OPENAI_API_KEY", os.getenv("LLM_API_KEY", ""))


def resolve_openai_base_url() -> str:
    base_url = os.getenv(
        "OPENAI_BASE_URL",
        os.getenv("OPENAI_API_URL", "https://api.openai.com/v1"),
    )
    base_url = _trim_trailing_slash(base_url)
    if base_url.endswith("/chat/completions"):
        return base_url[: -len("/chat/completions")]
    return base_url


def resolve_openai_chat_url() -> str:
    return f"{resolve_openai_base_url()}/chat/completions"


def resolve_anthropic_api_url() -> str:
    return os.getenv(
        "ANTHROPIC_API_URL",
        "https://api.anthropic.com/v1/messages",
    )


def load_llm_config(provider: Optional[str] = None) -> Dict[str, Any]:
    resolved_provider = resolve_provider(provider)

    if resolved_provider == "anthropic":
        return {
            "provider": "anthropic",
            "model": os.getenv(
                "ANTHROPIC_MODEL",
                os.getenv("LLM_MODEL", "claude-sonnet-4-20250514"),
            ),
            "api_url": resolve_anthropic_api_url(),
            "base_url": resolve_anthropic_api_url(),
            "max_tokens": _env_int("LLM_MAX_TOKENS", 2048),
            "temperature": _env_float("LLM_TEMPERATURE", 0.7),
            "timeout_seconds": _env_float("LLM_TIMEOUT_SECONDS", 30.0),
        }

    return {
        "provider": "openai",
        "model": os.getenv(
            "OPENAI_MODEL",
            os.getenv("LLM_MODEL", "gpt-4.1-mini"),
        ),
        "api_url": resolve_openai_chat_url(),
        "base_url": resolve_openai_base_url(),
        "max_tokens": _env_int("LLM_MAX_TOKENS", 2048),
        "temperature": _env_float("LLM_TEMPERATURE", 0.7),
        "timeout_seconds": _env_float("LLM_TIMEOUT_SECONDS", 30.0),
    }
