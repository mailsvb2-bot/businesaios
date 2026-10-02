"""Canonical runtime surface for LLM contracts and provider factory helpers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace

from core.llm import (
    LLMClient,
    ModelCapability,
    ModelCapabilityRegistry,
    ModelEvaluation,
    ModelPolicy,
    ModelProfile,
    ModelProvider,
    ModelRouteDecision,
    ModelRouter,
    ModelRouteRequest,
    build_anthropic_client,
    build_gigachat_client,
    build_openai_compat,
    build_yandexgpt_client,
)
from core.llm.agent.agent import LLMAgent, LLMAgentConfig
from core.llm.contracts import LLMMessage, LLMRequest, LLMResponse
from runtime.public_api_alias import install_public_api_alias

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

    read_value(name, default) may read from env, settings, or a merged source.
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

    anthropic_version = (
        str(read_value("ANTHROPIC_VERSION", "2023-06-01") or "").strip()
        or "2023-06-01"
    )
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



class RoutedLLMClient:
    """Runtime adapter: pure core routing plus the actual provider call."""

    def __init__(
        self,
        *,
        router: ModelRouter,
        clients_by_profile_id: Mapping[str, LLMClient],
        policy: ModelPolicy,
    ) -> None:
        self._router = router
        self._clients = dict(clients_by_profile_id)
        self._policy = policy

    @staticmethod
    def _route_request(req: LLMRequest) -> ModelRouteRequest:
        metadata = dict(req.metadata or {})
        raw_capabilities = metadata.get("required_model_capabilities") or ()
        return ModelRouteRequest(
            required_capabilities=frozenset(ModelCapability(str(value)) for value in raw_capabilities),
            context_tokens=int(metadata.get("context_tokens") or 0),
            estimated_input_tokens=int(metadata.get("estimated_input_tokens") or 0),
            estimated_output_tokens=int(metadata.get("estimated_output_tokens") or req.max_tokens or 0),
            privacy_class=str(metadata.get("privacy_class") or "internal"),
            jurisdiction=str(metadata.get("jurisdiction") or "*"),
            preferred_profile_id=str(metadata["preferred_model_profile_id"]) if metadata.get("preferred_model_profile_id") else req.model_profile_id,
            pinned_profile_id=str(metadata["pinned_model_profile_id"]) if metadata.get("pinned_model_profile_id") else None,
        )

    @staticmethod
    def _request_for_profile(req: LLMRequest, decision: ModelRouteDecision) -> LLMRequest:
        metadata = dict(req.metadata or {})
        metadata.update({
            "model_profile_id": decision.profile.profile_id,
            "model_provider": decision.profile.provider,
            "model_version": decision.profile.model_version,
            "model_policy_id": decision.policy_id,
            "model_policy_version": decision.policy_version,
            "model_fallback_from_profile_id": decision.fallback_from_profile_id,
        })
        return replace(req, model=decision.profile.model, model_profile_id=decision.profile.profile_id, metadata=metadata)

    @staticmethod
    def _response_with_route(response: LLMResponse, decision: ModelRouteDecision) -> LLMResponse:
        raw = dict(response.raw or {})
        raw["model_route"] = {
            "profile_id": decision.profile.profile_id,
            "provider": decision.profile.provider,
            "model": decision.profile.model,
            "model_version": decision.profile.model_version,
            "estimated_cost": decision.estimated_cost,
            "policy_id": decision.policy_id,
            "policy_version": decision.policy_version,
            "fallback_from_profile_id": decision.fallback_from_profile_id,
        }
        return replace(response, raw=raw)

    def _client_for(self, decision: ModelRouteDecision) -> LLMClient:
        try:
            return self._clients[decision.profile.profile_id]
        except KeyError as exc:
            raise RuntimeError(f"model client is not registered for profile: {decision.profile.profile_id}") from exc

    def generate_sync(self, req: LLMRequest) -> LLMResponse:
        decision = self._router.route(self._route_request(req), policy=self._policy)
        response = self._client_for(decision).generate_sync(self._request_for_profile(req, decision))
        return self._response_with_route(response, decision)

    async def generate(self, req: LLMRequest) -> LLMResponse:
        decision = self._router.route(self._route_request(req), policy=self._policy)
        response = await self._client_for(decision).generate(self._request_for_profile(req, decision))
        return self._response_with_route(response, decision)


__all__ = [
    "CANON_RUNTIME_LLM_NAMESPACE",
    "LLMClient",
    "LLMMessage",
    "LLMRequest",
    "LLMAgent",
    "LLMAgentConfig",
    "ModelCapability",
    "ModelCapabilityRegistry",
    "ModelEvaluation",
    "ModelPolicy",
    "ModelProfile",
    "ModelProvider",
    "ModelRouteDecision",
    "ModelRouteRequest",
    "ModelRouter",
    "RoutedLLMClient",
    "Transport",
    "normalize_provider",
    "resolve_runtime_llm_settings",
    "build_runtime_llm_client",
]

CANON_RUNTIME_LLM_NAMESPACE = True

install_public_api_alias(__name__)
