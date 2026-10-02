"""Single public facade for pure LLM provider adapters."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from config.llm_provider_policy import DEFAULT_LLM_PROVIDER_POLICY, LLMProviderPolicy

from .contracts import LLMClient
from .providers.anthropic import AnthropicClient, AnthropicTransport, build_anthropic
from .providers.gigachat import GigaChatClient, GigaChatTransport, build_gigachat
from .providers.mock import MockLLMClient
from .providers.openai_provider import OpenAICompatClient, OpenAICompatConfig
from .providers.yandexgpt import YandexGPTClient, YandexGPTTransport, build_yandexgpt

OpenAICompatTransport = Callable[[str, str, dict[str, Any], int], dict[str, Any]]


def build_openai_compat(*, base_url: str, api_key: str, default_model: str | None = None, transport: OpenAICompatTransport | None = None, policy: LLMProviderPolicy = DEFAULT_LLM_PROVIDER_POLICY) -> LLMClient:
    return OpenAICompatClient(OpenAICompatConfig(base_url=base_url, api_key=api_key, default_model=default_model or policy.default_openai_compat_model, transport=transport))


def build_mock(*, fixed_text: str | None = None, raise_error: bool = False, policy: LLMProviderPolicy = DEFAULT_LLM_PROVIDER_POLICY) -> LLMClient:
    return MockLLMClient(fixed_text=fixed_text or policy.mock_fixed_text, raise_error=raise_error)


def build_anthropic_client(*, base_url: str, api_key: str, default_model: str, transport: AnthropicTransport, anthropic_version: str | None = None, timeout_s: int | None = None, policy: LLMProviderPolicy = DEFAULT_LLM_PROVIDER_POLICY) -> LLMClient:
    return build_anthropic(transport=transport, base_url=base_url, api_key=api_key, model=default_model, anthropic_version=anthropic_version, timeout_s=timeout_s or policy.default_timeout_s)


def build_gigachat_client(*, base_url: str, api_key: str, default_model: str, transport: GigaChatTransport, timeout_s: int | None = None, policy: LLMProviderPolicy = DEFAULT_LLM_PROVIDER_POLICY) -> LLMClient:
    return build_gigachat(transport=transport, base_url=base_url, api_key=api_key, model=default_model, timeout_s=timeout_s or policy.default_timeout_s)


def build_yandexgpt_client(*, base_url: str, api_key: str, default_model: str, transport: YandexGPTTransport, timeout_s: int | None = None, policy: LLMProviderPolicy = DEFAULT_LLM_PROVIDER_POLICY) -> LLMClient:
    return build_yandexgpt(transport=transport, base_url=base_url, api_key=api_key, model=default_model, timeout_s=timeout_s or policy.default_timeout_s)


__all__ = [
    "AnthropicClient", "AnthropicTransport", "GigaChatClient", "GigaChatTransport",
    "MockLLMClient", "OpenAICompatClient", "OpenAICompatConfig", "OpenAICompatTransport",
    "YandexGPTClient", "YandexGPTTransport", "build_anthropic_client", "build_gigachat_client",
    "build_mock", "build_openai_compat", "build_yandexgpt_client",
]
