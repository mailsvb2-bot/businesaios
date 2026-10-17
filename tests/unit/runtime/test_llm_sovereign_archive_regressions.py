"""Additional archive-origin provider proofs omitted by the earlier merge."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.llm.contracts import LLMMessage, LLMRequest
from runtime._internal import llm_transport
from runtime.effects import llm_effects
from runtime.llm import build_runtime_llm_client


def test_yandex_facade_posts_correct_endpoint_and_payload(monkeypatch):
    sent = []
    def fake_http(*, url, headers, data, timeout_s):
        sent.append((url, headers, data))
        return SimpleNamespace(status=200, json={"result": {"alternatives": [{"message": {"text": "готово"}}]}}, text="")
    monkeypatch.setattr(llm_transport, "sync_post_json", fake_http)
    result = llm_effects.llm_generate_yandexgpt(
        base_url="https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
        api_key="dummy", payload={"modelUri": "gpt://folder/yandexgpt-lite/latest", "messages": []})
    assert result["result"]["alternatives"][0]["message"]["text"] == "готово"
    assert sent[0][0] == "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    assert sent[0][1]["Authorization"] == "Api-Key dummy"


def test_gigachat_uses_one_chat_path_and_oauth_bearer(monkeypatch):
    requested = []
    monkeypatch.setattr(llm_transport, "_gigachat_access_token", lambda key, timeout: "access-token")
    def fake_http(*, url, headers, data, timeout_s):
        requested.append((url, headers))
        return SimpleNamespace(status=200, json={"choices": [{"message": {"content": "ok"}}]}, text="")
    monkeypatch.setattr(llm_transport, "sync_post_json", fake_http)
    client = build_runtime_llm_client(
        provider="gigachat", base_url="https://gigachat.devices.sberbank.ru/api/v1",
        api_key="authorization-key", model="GigaChat",
        gigachat_transport=lambda url, key, payload, timeout: llm_effects.llm_generate_gigachat(
            base_url=url, api_key=key, payload=payload, timeout_s=timeout),
    )
    result = client.generate_sync(LLMRequest(messages=[LLMMessage(role="user", content="Привет")], model="GigaChat"))
    assert result.content == "ok"
    assert requested == [("https://gigachat.devices.sberbank.ru/api/v1/chat/completions", {
        "Authorization": "Bearer access-token", "Content-Type": "application/json",
        "User-Agent": "businesaios/llm-gigachat",
    })] or (len(requested) == 1 and requested[0][0].endswith("/api/v1/chat/completions")
            and requested[0][1]["Authorization"] == "Bearer access-token")


@pytest.mark.parametrize("provider,base", [
    ("openai_compat", "https://api.openai.com/v1"),
    ("openai_compat", "https://evil.example/?next=.yandex.net"),
    ("anthropic", "https://api.anthropic.com"),
])
def test_unapproved_provider_never_reaches_transport(monkeypatch, provider, base):
    monkeypatch.delenv("LLM_ALLOW_FOREIGN_PROVIDERS", raising=False)
    with pytest.raises(RuntimeError):
        build_runtime_llm_client(provider=provider, base_url=base, api_key="dummy", model="model",
                                 openai_transport=lambda *_: pytest.fail("network must not execute"),
                                 anthropic_transport=lambda *_: pytest.fail("network must not execute"))
