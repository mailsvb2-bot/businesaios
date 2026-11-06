from core.llm.redaction import redact_text, safe_metadata


def test_redact_email_phone_tokenlike():
    s = "email a@b.com phone +31 6 1234 5678 key sk-ABCDEF1234567890"
    r = redact_text(s)
    assert "<EMAIL_" in r.text
    assert "<PHONE_" in r.text
    assert "<SECRET_" in r.text
    assert "a@b.com" not in r.text
    assert "sk-" not in r.text



def test_provider_metadata_allowlist_drops_secrets_and_private_identity():
    sensitive = {
        "api_key": "canary-credential-123",
        "authorization": "Bearer canary-token",
        "refresh_token": "canary-refresh",
        "tenant_id": "private-tenant",
        "user_id": "private-user",
        "email": "private@example.com",
        "prompt": "confidential",
        "task_type": "ads.creative.generate",
        "context_tokens": 42,
    }
    assert safe_metadata(sensitive) == {"context_tokens": 42}
    assert safe_metadata({"context_tokens": True}) == {}
    assert safe_metadata({"context_tokens": -1}) == {}
    assert safe_metadata({"context_tokens": 10_000_001}) == {}
    assert safe_metadata({"context_tokens": "42"}) == {}


def test_openai_compatible_provider_does_not_forward_untrusted_metadata():
    from core.llm import LLMMessage, LLMRequest, OpenAICompatClient, OpenAICompatConfig

    captured = {}

    def transport(_url, _key, payload, _timeout):
        captured.update(payload)
        return {"output_text": "ok", "usage": {
            "input_tokens": 1, "output_tokens": 1, "total_tokens": 2,
        }}

    client = OpenAICompatClient(OpenAICompatConfig(
        base_url="https://api.openai.com/v1/responses", api_key="test-key", transport=transport,
    ))
    client.generate_sync(LLMRequest(
        model="test-model", messages=[LLMMessage(role="user", content="hello")],
        metadata={"api_key": "private-api-key", "tenant_id": "private-tenant",
                  "user_id": "private-user", "context_tokens": 7},
    ))
    assert captured["metadata"] == {"context_tokens": 7}
    assert "private-api-key" not in repr(captured)
    assert "private-user" not in repr(captured)
