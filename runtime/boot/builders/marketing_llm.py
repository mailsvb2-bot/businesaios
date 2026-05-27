from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True

"""Builders for optional LLM-powered marketing components.

Kept separate from the main system_builder to avoid 'god-module' growth.

Important: this module must NOT import network libraries.
All network I/O is executed via runtime.effects -> sealed runtime/_internal.
"""

from typing import Any, Optional

from runtime.llm import (
    LLMAgent,
    LLMAgentConfig,
    build_runtime_llm_client,
    normalize_provider,
    resolve_runtime_llm_settings,
)
from runtime.observability.error_handling import swallow
from runtime.platform.config.env_flags import env_bool, env_float, env_int, env_str


def _setting_or_env(settings: Any, name: str, default: str = "") -> str:
    value = getattr(settings, name, None)
    if value is None:
        return env_str(name, default)
    return str(value)


def _setting_or_env_bool(settings: Any, *names: str, default: bool = False) -> bool:
    for name in names:
        value = getattr(settings, name, None)
        if value is not None:
            return str(value).strip().lower() in {"1", "true", "yes"}
    for name in names:
        if env_bool(name, False):
            return True
    return bool(default)


def _runtime_timeout_s(settings: Any) -> int:
    for name in ("LLM_TIMEOUT_S", "MARKETING_LLM_TIMEOUT_S"):
        value = getattr(settings, name, None)
        if value is not None:
            try:
                return int(max(1, int(value)))
            except (TypeError, ValueError):
                continue
    configured = env_int("LLM_TIMEOUT_S", 0)
    if configured > 0:
        return int(configured)
    configured = env_int("MARKETING_LLM_TIMEOUT_S", 0)
    if configured > 0:
        return int(configured)
    return 25


def _provider_settings(settings: Any) -> tuple[str, str, str, str, str | None]:
    provider = normalize_provider(
        _setting_or_env(settings, "LLM_PROVIDER", _setting_or_env(settings, "MARKETING_LLM_PROVIDER", "openai_compat"))
    )
    return resolve_runtime_llm_settings(
        provider=provider,
        read_value=lambda name, default: _setting_or_env(settings, name, default),
        openai_legacy_keys=("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"),
    )


def _build_llm_client(*, settings: Any):
    from runtime.effects import (
        llm_generate_anthropic,
        llm_generate_gigachat,
        llm_generate_openai_compat,
        llm_generate_yandexgpt,
    )

    provider, base_url, api_key, model, anthropic_version = _provider_settings(settings)
    return provider, model, build_runtime_llm_client(
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout_s=_runtime_timeout_s(settings),
        anthropic_version=anthropic_version,
        openai_transport=lambda bu, ak, payload, timeout_s: llm_generate_openai_compat(base_url=bu, api_key=ak, payload=payload, timeout_s=int(timeout_s)),
        anthropic_transport=lambda bu, ak, payload, timeout_s: llm_generate_anthropic(base_url=bu, api_key=ak, payload=payload, timeout_s=int(timeout_s)),
        gigachat_transport=lambda bu, ak, payload, timeout_s: llm_generate_gigachat(base_url=bu, api_key=ak, payload=payload, timeout_s=int(timeout_s)),
        yandexgpt_transport=lambda bu, ak, payload, timeout_s: llm_generate_yandexgpt(base_url=bu, api_key=ak, payload=payload, timeout_s=int(timeout_s)),
    )


def build_marketing_llm_composer(*, settings: Any, event_store: Any, logger: Any):
    """Build optional MarketingLLMComposer (or return None)."""

    try:
        enabled = _setting_or_env_bool(settings, "LLM_ENABLED", "LLM_MARKETING_ENABLED", default=False)
    except (AttributeError, TypeError, ValueError):
        enabled = False
    if not enabled:
        return None

    try:
        provider, model, llm = _build_llm_client(settings=settings)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        try:
            logger.warning("LLM disabled due to invalid runtime wiring", extra={"error": type(exc).__name__, "detail": str(exc)[:200]})
        except (AttributeError, TypeError, ValueError):
            swallow(__name__, "runtime/boot/builders/marketing_llm.py")
        return None

    from runtime.marketing import LLMComposerConfig, MarketingLLMComposer

    try:
        logger.info("LLM enabled", extra={"provider": provider, "model": model})
    except (AttributeError, TypeError, ValueError):
        swallow(__name__, "runtime/boot/builders/marketing_llm.py")

    cfg = LLMComposerConfig(
        model=model,
        provider=provider,
        global_rps=env_float("LLM_GLOBAL_RPS", 15.0),
        global_burst=env_int("LLM_GLOBAL_BURST", 20),
        tenant_rps=env_float("LLM_TENANT_RPS", 4.0),
        tenant_burst=env_int("LLM_TENANT_BURST", 6),
        budget_source=_setting_or_env(settings, "LLM_BUDGET_SOURCE", "auto") or "auto",
    )
    return MarketingLLMComposer(llm, cfg, event_store=event_store)


def build_marketing_llm_agent(*, settings: Any, event_store: Any, logger: Any) -> Optional[Any]:
    """Build canonical LLMAgent facade (Variant B).

    We reuse the same underlying LLM client wiring as the composer to avoid
    divergence (no "two truths").
    """

    composer = build_marketing_llm_composer(settings=settings, event_store=event_store, logger=logger)
    if composer is None:
        return None

    llm_client = composer.llm_client
    provider, _base_url, _api_key, agent_model, _anthropic_version = _provider_settings(settings)
    cfg = LLMAgentConfig(
        default_model=agent_model,
        temperature=env_float("LLM_TEMPERATURE", 0.4),
        max_tokens=env_int("LLM_MAX_TOKENS", 700),
        timeout_s=float(_runtime_timeout_s(settings)),
    )
    return LLMAgent(llm_client, cfg)
