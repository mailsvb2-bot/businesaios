from __future__ import annotations

from runtime.public_api_alias import install_public_api_alias

"""Canonical runtime surface for LLM contracts and provider factory helpers."""

from typing import Callable, Dict, Optional

from core.llm import (
    LLMClient,
    build_anthropic_client,
    build_gigachat_client,
    build_openai_compat,
    build_yandexgpt_client,
)
from core.llm.agent.agent import LLMAgent, LLMAgentConfig
from core.llm.contracts import LLMMessage, LLMRequest

Transport = Callable[[str, str, dict[str, object], int], dict[str, object]]

_PROVIDER_DEFAULTS = {
    "openai_compat": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4.1-mini",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com",
        "model": "claude-3-5-sonnet-latest",
    },
    "gigachat": {
        "base_url": "https://gigachat.devices.sberbank.ru/api/v1",
        "model": "GigaChat",
    },
    "yandexgpt": {
        "base_url": "",
        "model": "yandexgpt-lite",
    },
}

_PROVIDER_KEYS = {
    "openai_compat": ("OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL"),
    "anthropic": ("ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"),
    "gigachat": ("GIGACHAT_BASE_URL", "GIGACHAT_API_KEY", "GIGACHAT_MODEL"),
    "yandexgpt": ("YANDEXGPT_BASE_URL", "YANDEXGPT_API_KEY", "YANDEXGPT_MODEL"),
}


def normalize_provider(provider: str | None) -> str:
    value = str(provider or "openai_compat").strip().lower()
    aliases = {
        "openai": "openai_compat",
        "openai_compat": "openai_compat",
        "anthropic": "anthropic",
        "claude": "anthropic",
        "giga": "gigachat",
        "gigachat": "gigachat",
        "yandex": "yandexgpt",
        "yandexgpt": "yandexgpt",
    }
    return aliases.get(value, value or "openai_compat")


def resolve_runtime_llm_settings(
    *,
    provider: str | None,
    read_value: Callable[[str, str], str],
    model_override: str | None = None,
    openai_legacy_keys: tuple[str, str, str] | None = None,
) -> tuple[str, str, str, str, str | None]:
    """Resolve provider settings without forking mapping logic.

    ``read_value(name, default)`` may read from env, settings, or a merged source.
    This keeps provider defaults and key selection canonical while allowing both
    runtime boot and sealed actions to supply their own configuration source.
    """

    normalized = normalize_provider(provider)
    base_key, api_key_key, model_key = _PROVIDER_KEYS[normalized]
    defaults = _PROVIDER_DEFAULTS[normalized]

    base_url = str(read_value(base_key, defaults["base_url"]) or "").strip()
    api_key = str(read_value(api_key_key, "") or "").strip()
    model = str(model_override or read_value(model_key, defaults["model"]) or "").strip()

    if normalized == "openai_compat" and openai_legacy_keys is not None:
        legacy_base, legacy_key, legacy_model = openai_legacy_keys
        base_url = str(read_value(legacy_base, base_url) or "").strip() or base_url
        api_key = str(read_value(legacy_key, api_key) or "").strip() or api_key
        model = str(model_override or read_value(legacy_model, model) or "").strip() or model

    anthropic_version = str(read_value("ANTHROPIC_VERSION", "2023-06-01") or "").strip() or "2023-06-01"
    return normalized, base_url, api_key, model, anthropic_version


def build_runtime_llm_client(
    *,
    provider: str,
    base_url: str,
    api_key: str,
    model: str,
    timeout_s: int = 20,
    anthropic_version: str | None = None,
    openai_transport: Transport | None = None,
    anthropic_transport: Transport | None = None,
    gigachat_transport: Transport | None = None,
    yandexgpt_transport: Transport | None = None,
) -> LLMClient:
    normalized = normalize_provider(provider)
    base = str(base_url or "").strip()
    key = str(api_key or "").strip()
    default_model = str(model or "").strip()
    if not base:
        raise RuntimeError("llm_base_url_missing")
    if not key:
        raise RuntimeError("llm_api_key_missing")
    if not default_model:
        raise RuntimeError("llm_model_missing")

    if normalized == "openai_compat":
        if openai_transport is None:
            raise RuntimeError("llm_transport_missing:openai_compat")
        return build_openai_compat(
            base_url=base,
            api_key=key,
            default_model=default_model,
            transport=openai_transport,
        )
    if normalized == "anthropic":
        if anthropic_transport is None:
            raise RuntimeError("llm_transport_missing:anthropic")
        return build_anthropic_client(
            base_url=base,
            api_key=key,
            default_model=default_model,
            transport=anthropic_transport,
            anthropic_version=anthropic_version,
            timeout_s=int(timeout_s or 20),
        )
    if normalized == "gigachat":
        if gigachat_transport is None:
            raise RuntimeError("llm_transport_missing:gigachat")
        return build_gigachat_client(
            base_url=base,
            api_key=key,
            default_model=default_model,
            transport=gigachat_transport,
            timeout_s=int(timeout_s or 20),
        )
    if normalized == "yandexgpt":
        if yandexgpt_transport is None:
            raise RuntimeError("llm_transport_missing:yandexgpt")
        return build_yandexgpt_client(
            base_url=base,
            api_key=key,
            default_model=default_model,
            transport=yandexgpt_transport,
            timeout_s=int(timeout_s or 20),
        )
    raise RuntimeError(f"llm_provider_unsupported:{normalized}")


__all__ = [
    'CANON_RUNTIME_LLM_NAMESPACE',
    "LLMClient",
    "LLMMessage",
    "LLMRequest",
    "LLMAgent",
    "LLMAgentConfig",
    "Transport",
    "normalize_provider",
    "resolve_runtime_llm_settings",
    "build_runtime_llm_client",
]

CANON_RUNTIME_LLM_NAMESPACE = True




install_public_api_alias(__name__)
