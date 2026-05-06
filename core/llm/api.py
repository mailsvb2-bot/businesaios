"""Public LLM facade API.

This module is the single public surface for building provider clients.

Design constraints:
- core/llm/** stays pure (no network IO).
- Provider clients receive a transport callable injected from sealed runtime effects.
- Outside core/llm/**, code must not import providers directly.
"""

from __future__ import annotations

from config.llm_provider_policy import DEFAULT_LLM_PROVIDER_POLICY, LLMProviderPolicy
from .contracts import LLMClient
from .providers.mock import MockLLMClient as _MockAdapter
from .providers.openai_compat import OpenAICompatClient, OpenAICompatConfig
from .providers.anthropic import AnthropicClient, AnthropicTransport
from .providers.gigachat import GigaChatClient, GigaChatTransport
from .providers.yandexgpt import YandexGPTClient, YandexGPTTransport
from .service import (
    OpenAICompatTransport,
    build_anthropic_provider as _assemble_anthropic,
    build_gigachat_provider as _assemble_gigachat,
    build_mock_client as _assemble_mock,
    build_openai_compat_client as _assemble_openai_compat,
    build_yandexgpt_provider as _assemble_yandexgpt,
)

MockLLMClient = _MockAdapter


def build_openai_compat(*, base_url: str, api_key: str, default_model: str | None = None, transport: OpenAICompatTransport | None = None, policy: LLMProviderPolicy = DEFAULT_LLM_PROVIDER_POLICY) -> LLMClient:
    return _assemble_openai_compat(base_url=base_url, api_key=api_key, default_model=default_model or policy.default_openai_compat_model, transport=transport, policy=policy)


def build_mock(*, fixed_text: str | None = None, raise_error: bool = False, policy: LLMProviderPolicy = DEFAULT_LLM_PROVIDER_POLICY) -> LLMClient:
    return _assemble_mock(fixed_text=fixed_text or policy.mock_fixed_text, raise_error=raise_error)


def build_anthropic_client(*, base_url: str, api_key: str, default_model: str, transport: AnthropicTransport, anthropic_version: str | None = None, timeout_s: int | None = None, policy: LLMProviderPolicy = DEFAULT_LLM_PROVIDER_POLICY) -> LLMClient:
    return _assemble_anthropic(transport=transport, base_url=base_url, api_key=api_key, default_model=default_model, anthropic_version=anthropic_version, timeout_s=timeout_s or policy.default_timeout_s)


def build_gigachat_client(*, base_url: str, api_key: str, default_model: str, transport: GigaChatTransport, timeout_s: int | None = None, policy: LLMProviderPolicy = DEFAULT_LLM_PROVIDER_POLICY) -> LLMClient:
    return _assemble_gigachat(transport=transport, base_url=base_url, api_key=api_key, default_model=default_model, timeout_s=timeout_s or policy.default_timeout_s)


def build_yandexgpt_client(*, base_url: str, api_key: str, default_model: str, transport: YandexGPTTransport, timeout_s: int | None = None, policy: LLMProviderPolicy = DEFAULT_LLM_PROVIDER_POLICY) -> LLMClient:
    return _assemble_yandexgpt(transport=transport, base_url=base_url, api_key=api_key, default_model=default_model, timeout_s=timeout_s or policy.default_timeout_s)


__all__ = [
    "OpenAICompatClient",
    "OpenAICompatConfig",
    "OpenAICompatTransport",
    "AnthropicClient",
    "AnthropicTransport",
    "GigaChatClient",
    "GigaChatTransport",
    "YandexGPTClient",
    "YandexGPTTransport",
    "build_openai_compat",
    "build_mock",
    "build_anthropic_client",
    "build_gigachat_client",
    "build_yandexgpt_client",
]
