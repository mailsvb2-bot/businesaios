from __future__ import annotations

"""Canonical provider service layer for public LLM builders."""

from typing import Any, Callable, Dict, Optional

from config.llm_provider_policy import DEFAULT_LLM_PROVIDER_POLICY, LLMProviderPolicy
from .contracts import LLMClient
from .providers.anthropic import AnthropicTransport, build_anthropic
from .providers.gigachat import GigaChatTransport, build_gigachat
from .providers.mock import MockLLMClient
from .providers.openai_provider import OpenAICompatClient, OpenAICompatConfig
from .providers.yandexgpt import YandexGPTTransport, build_yandexgpt

OpenAICompatTransport = Callable[[str, str, Dict[str, Any], int], Dict[str, Any]]


def build_openai_compat_client(
    *,
    base_url: str,
    api_key: str,
    default_model: str | None = None,
    transport: Optional[OpenAICompatTransport] = None,
    policy: LLMProviderPolicy = DEFAULT_LLM_PROVIDER_POLICY,
) -> LLMClient:
    cfg = OpenAICompatConfig(
        base_url=base_url,
        api_key=api_key,
        default_model=default_model or policy.default_openai_compat_model,
        transport=transport,
    )
    return OpenAICompatClient(cfg)


def build_mock_client(*, fixed_text: str | None = None, raise_error: bool = False, policy: LLMProviderPolicy = DEFAULT_LLM_PROVIDER_POLICY) -> LLMClient:
    return MockLLMClient(fixed_text=fixed_text or policy.mock_fixed_text, raise_error=raise_error)


def build_anthropic_provider(*, base_url: str, api_key: str, default_model: str, transport: AnthropicTransport, anthropic_version: str | None = None, timeout_s: int | None = None, policy: LLMProviderPolicy = DEFAULT_LLM_PROVIDER_POLICY) -> LLMClient:
    return build_anthropic(
        transport=transport,
        base_url=base_url,
        api_key=api_key,
        model=default_model,
        anthropic_version=anthropic_version,
        timeout_s=timeout_s or policy.default_timeout_s,
    )


def build_gigachat_provider(*, base_url: str, api_key: str, default_model: str, transport: GigaChatTransport, timeout_s: int | None = None, policy: LLMProviderPolicy = DEFAULT_LLM_PROVIDER_POLICY) -> LLMClient:
    return build_gigachat(transport=transport, base_url=base_url, api_key=api_key, model=default_model, timeout_s=timeout_s or policy.default_timeout_s)


def build_yandexgpt_provider(*, base_url: str, api_key: str, default_model: str, transport: YandexGPTTransport, timeout_s: int | None = None, policy: LLMProviderPolicy = DEFAULT_LLM_PROVIDER_POLICY) -> LLMClient:
    return build_yandexgpt(transport=transport, base_url=base_url, api_key=api_key, model=default_model, timeout_s=timeout_s or policy.default_timeout_s)


__all__ = [
    "OpenAICompatTransport",
    "build_openai_compat_client",
    "build_mock_client",
    "build_anthropic_provider",
    "build_gigachat_provider",
    "build_yandexgpt_provider",
]
