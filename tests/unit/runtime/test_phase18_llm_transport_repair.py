"""Regression proof for the canonical sealed Russian LLM transport."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime._internal import llm_transport
from runtime.effects import llm_effects
from runtime.llm import build_runtime_llm_client
from core.llm.providers.anthropic import _extract_usage as extract_anthropic_usage
from core.llm.providers.openai_provider import _extract_usage as extract_openai_usage


def test_effect_facade_reaches_sealed_transport(monkeypatch):
    calls = []
    monkeypatch.setattr(llm_transport, "llm_generate_yandexgpt", lambda **kw: calls.append(kw) or {"result": {}})
    result = llm_effects.llm_generate_yandexgpt(base_url="https://llm.api.cloud.yandex.net", api_key="demo", payload={})
    assert result == {"result": {}}
    assert len(calls) == 1


def test_gigachat_oauth_and_token_cache(monkeypatch):
    llm_transport._GIGACHAT_TOKENS.clear()
    network = []
    def fake_request(**kwargs):
        network.append(kwargs)
        return SimpleNamespace(status=200, json={"access_token": "token", "expires_at": 9999999999999})
    monkeypatch.setattr(llm_transport, "sync_request", fake_request)
    token = llm_transport._gigachat_access_token("key", 20)
    assert token == llm_transport._gigachat_access_token("key", 20) == "token"
    assert len(network) == 1
    assert network[0]["headers"]["Authorization"] == "Basic key"
    assert network[0]["url"].startswith("https://ngw.devices.sberbank.ru")


def test_gigachat_oauth_failure_blocks_chat(monkeypatch):
    llm_transport._GIGACHAT_TOKENS.clear()
    monkeypatch.setattr(llm_transport, "sync_request", lambda **_: SimpleNamespace(status=401, json={}))
    monkeypatch.setattr(llm_transport, "sync_post_json", lambda **_: pytest.fail("chat must never execute"))
    with pytest.raises(RuntimeError):
        llm_transport.llm_generate_gigachat(base_url="https://gigachat.devices.sberbank.ru/api/v1", api_key="invalid", payload={})


def test_foreign_host_fails_closed(monkeypatch):
    monkeypatch.delenv("LLM_ALLOW_FOREIGN_PROVIDERS", raising=False)
    monkeypatch.delenv("LLM_SOVEREIGN_HOSTS", raising=False)
    with pytest.raises(RuntimeError, match="non_sovereign"):
        build_runtime_llm_client(provider="openai_compat", base_url="https://api.openai.com/v1",
                                 api_key="fake", model="test", openai_transport=lambda *_: {})


def test_yandex_model_uri_and_metadata_not_sent(monkeypatch):
    monkeypatch.setenv("YANDEXGPT_FOLDER_ID", "folder")
    captured = []
    client = build_runtime_llm_client(provider="yandexgpt",
        base_url="https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
        api_key="dummy", model="yandexgpt-lite",
        yandexgpt_transport=lambda base, key, body, timeout: captured.append(body) or {"result": {"alternatives": [{"message": {"text": "ok"}}]}})
    from core.llm.contracts import LLMMessage, LLMRequest
    request = LLMRequest(messages=[LLMMessage(role="user", content="hello")], model="yandexgpt-lite", metadata={"tenant_id": "secret"})
    client.generate_sync(request)
    assert captured[0]["modelUri"] == "gpt://folder/yandexgpt-lite/latest"
    assert "metadata" not in captured[0]



def test_anthropic_cache_usage_is_normalized_without_dropping_tokens():
    usage = extract_anthropic_usage({
        "usage": {
            "input_tokens": 100,
            "output_tokens": 20,
            "cache_creation_input_tokens": 10,
            "cache_read_input_tokens": 40,
        }
    })
    assert usage is not None
    assert (usage.prompt_tokens, usage.completion_tokens, usage.total_tokens) == (150, 20, 170)
    assert usage.cached_input_tokens == 40
    assert usage.cache_write_input_tokens == 10


def test_anthropic_unknown_cache_creation_breakdown_fails_closed():
    assert extract_anthropic_usage({
        "usage": {
            "input_tokens": 100,
            "output_tokens": 20,
            "cache_creation_input_tokens": 10,
            "cache_read_input_tokens": 40,
            "cache_creation": {"ephemeral_5m_input_tokens": 10},
        }
    }) is None


def test_openai_cached_and_reasoning_tokens_are_preserved():
    usage = extract_openai_usage({
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
            "prompt_tokens_details": {"cached_tokens": 40},
            "completion_tokens_details": {"reasoning_tokens": 8},
        }
    })
    assert usage is not None
    assert usage.cached_input_tokens == 40
    assert usage.reasoning_output_tokens == 8
