"""LLM module (canonical).

Design goals:
- LLM is a pure service with an explicit contract.
- LLM providers contain *no* business logic.
- Network access is routed through the sealed runtime effects layer.
"""

from .contracts import (
    LLMClient,
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMUsage,
)

from .templated import TemplatedLLM
from .api import (
    AnthropicClient,
    AnthropicTransport,
    GigaChatClient,
    GigaChatTransport,
    MockLLMClient,
    OpenAICompatClient,
    OpenAICompatConfig,
    OpenAICompatTransport,
    YandexGPTClient,
    YandexGPTTransport,
    build_anthropic_client,
    build_gigachat_client,
    build_mock,
    build_openai_compat,
    build_yandexgpt_client,
)

__all__ = [
    'LLMClient',
    'LLMMessage',
    'LLMRequest',
    'LLMResponse',
    'LLMUsage',
    'OpenAICompatClient',
    'OpenAICompatConfig',
    'OpenAICompatTransport',
    'MockLLMClient',
    'build_openai_compat',
    'build_mock',
    'AnthropicClient',
    'AnthropicTransport',
    'build_anthropic_client',
    'GigaChatClient',
    'GigaChatTransport',
    'build_gigachat_client',
    'YandexGPTClient',
    'YandexGPTTransport',
    'build_yandexgpt_client',
    'TemplatedLLM',
]
