"""Regression proof for the canonical sealed Russian LLM transport."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime._internal import llm_transport
from runtime.effects import llm_effects
from runtime.llm import build_runtime_llm_client


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
