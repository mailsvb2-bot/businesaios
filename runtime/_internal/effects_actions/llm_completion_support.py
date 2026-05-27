from __future__ import annotations

from typing import Any, Dict, Tuple

from runtime._internal.llm_transport import (
    llm_generate_anthropic,
    llm_generate_gigachat,
    llm_generate_openai_compat,
    llm_generate_yandexgpt,
)
from runtime.llm import LLMMessage, LLMRequest
from runtime.llm_provider_factory import (
    build_runtime_llm_client,
    normalize_provider,
    resolve_runtime_llm_settings,
)
from runtime.platform.config.env_flags import env_int, env_str


def _effective_provider_name(provider_override: str | None) -> str:
    configured = str(provider_override or env_str("MARKETING_LLM_PROVIDER", env_str("LLM_PROVIDER", "openai_compat"))).strip()
    return normalize_provider(configured)


def _effective_timeout_s() -> int:
    configured = env_int("MARKETING_LLM_TIMEOUT_S", 0)
    if configured > 0:
        return int(configured)
    configured = env_int("LLM_TIMEOUT_S", 0)
    if configured > 0:
        return int(configured)
    return 20


def read_provider_and_model(*, provider_override: str | None, model_override: str | None = None) -> Tuple[str, str]:
    normalized, _base_url, _api_key, effective_model, _anthropic_version = resolve_runtime_llm_settings(
        provider=_effective_provider_name(provider_override),
        model_override=model_override,
        read_value=lambda name, default: env_str(name, default),
        openai_legacy_keys=("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"),
    )
    return normalized, effective_model


def _provider_config(provider: str, model_override: str | None) -> tuple[str, str, str, str, str | None]:
    return resolve_runtime_llm_settings(
        provider=_effective_provider_name(provider),
        model_override=model_override,
        read_value=lambda name, default: env_str(name, default),
        openai_legacy_keys=("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"),
    )


def _client_for(*, provider: str, model: str | None):
    normalized, base_url, api_key, effective_model, anthropic_version = _provider_config(provider, model)
    if not api_key:
        return normalized, effective_model, None, "missing_api_key"
    if not base_url:
        return normalized, effective_model, None, "missing_base_url"
    try:
        client = build_runtime_llm_client(
            provider=normalized,
            base_url=base_url,
            api_key=api_key,
            model=effective_model,
            timeout_s=_effective_timeout_s(),
            anthropic_version=anthropic_version,
            openai_transport=lambda bu, ak, payload, timeout_s: llm_generate_openai_compat(base_url=bu, api_key=ak, payload=payload, timeout_s=int(timeout_s)),
            anthropic_transport=lambda bu, ak, payload, timeout_s: llm_generate_anthropic(base_url=bu, api_key=ak, payload=payload, timeout_s=int(timeout_s)),
            gigachat_transport=lambda bu, ak, payload, timeout_s: llm_generate_gigachat(base_url=bu, api_key=ak, payload=payload, timeout_s=int(timeout_s)),
            yandexgpt_transport=lambda bu, ak, payload, timeout_s: llm_generate_yandexgpt(base_url=bu, api_key=ak, payload=payload, timeout_s=int(timeout_s)),
        )
        return normalized, effective_model, client, None
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        return normalized, effective_model, None, type(exc).__name__


def call_marketing_llm(*, provider: str, system: str, user: str, model: str | None) -> Dict[str, Any]:
    normalized, effective_model, client, err = _client_for(provider=provider, model=model)
    if client is None:
        return {"ok": False, "error": str(err or "disabled"), "provider": normalized, "model": effective_model}

    req = LLMRequest(
        messages=[
            LLMMessage(role="system", content=str(system)[:8000]),
            LLMMessage(role="user", content=str(user)[:8000]),
        ],
        model=effective_model,
        temperature=0.2,
        max_tokens=600,
        timeout_s=float(_effective_timeout_s()),
        metadata={"surface": "marketing_llm_complete", "provider": normalized},
    )
    try:
        response = client.generate_sync(req)
        return {
            "ok": True,
            "provider": normalized,
            "model": effective_model,
            "text": str(getattr(response, "content", "") or "").strip(),
            "finish_reason": str(getattr(response, "finish_reason", "stop") or "stop"),
            "usage": getattr(response, "usage", None),
        }
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        return {"ok": False, "provider": normalized, "model": effective_model, "error": type(exc).__name__}


def emit_marketing_llm_success(*, event_log: Any, admin_id: str, decision_id: str, correlation_id: str, provider: str, model: str, text: str) -> None:
    event_log.emit(
        event_type="marketing_llm_completed",
        source="marketing.llm",
        user_id=str(admin_id or "system"),
        decision_id=str(decision_id or "-"),
        correlation_id=str(correlation_id or (decision_id or "-")),
        payload={"provider": str(provider), "model": str(model), "len": int(len(text))},
    )


def emit_marketing_llm_error(*, event_log: Any, admin_id: str, provider: str, model: str, error_name: str) -> None:
    event_log.emit_error(
        event_type="marketing_llm_error",
        details={"provider": str(provider), "model": str(model), "error": str(error_name)},
        source="marketing.llm",
        user_id=str(admin_id or "system"),
    )
