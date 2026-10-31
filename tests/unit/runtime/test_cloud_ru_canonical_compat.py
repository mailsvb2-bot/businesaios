"""Cloud.ru compatibility stays on the canonical OpenAI-compatible client and sealed transport."""
from types import SimpleNamespace

from core.llm.contracts import LLMMessage, LLMRequest
from core.llm.providers.openai_provider import OpenAICompatClient, OpenAICompatConfig
from runtime._internal import llm_transport


def test_cloud_ru_chat_payload_and_existing_responses_payload():
    request = LLMRequest(messages=[LLMMessage(role="user", content="привет")],
                         metadata={"tenant_id": "do-not-send"}, max_tokens=30)
    cloud = OpenAICompatClient(OpenAICompatConfig(
        base_url="https://foundation-models.api.cloud.ru/v1", api_key="x"))
    cloud_payload = cloud._payload_for(request)
    assert cloud_payload["messages"] == [{"role": "user", "content": "привет"}]
    assert cloud_payload["max_tokens"] == 30
    assert "input" not in cloud_payload and "metadata" not in cloud_payload
    assert "max_output_tokens" not in cloud_payload
    legacy = OpenAICompatClient(OpenAICompatConfig(
        base_url="https://api.openai.com/v1", api_key="x"))._payload_for(request)
    assert "input" in legacy and "messages" not in legacy
    assert legacy["max_output_tokens"] == 30


def test_cloud_ru_sealed_endpoint_and_other_provider_backward_compat(monkeypatch):
    urls = []
    def post(**kw):
        urls.append(kw["url"])
        return SimpleNamespace(status=200, json={"choices": [
            {"message": {"content": "ok"}, "finish_reason": "stop"}]}, text="")
    monkeypatch.setattr(llm_transport, "sync_post_json", post)
    for base in (
        "https://foundation-models.api.cloud.ru/v1",
        "https://foundation-models.api.cloud.ru/v1/chat/completions/",
        "https://api.openai.com/v1",
    ):
        llm_transport.llm_generate_openai_compat(
            base_url=base, api_key="x", payload={"model": "m"})
    assert urls == [
        "https://foundation-models.api.cloud.ru/v1/chat/completions",
        "https://foundation-models.api.cloud.ru/v1/chat/completions",
        "https://api.openai.com/v1/responses",
    ]
