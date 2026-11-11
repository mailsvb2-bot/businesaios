from core.llm.redaction import redact_text


def test_redact_email_phone_tokenlike():
    s = "email a@b.com phone +31 6 1234 5678 key sk-ABCDEF1234567890"
    r = redact_text(s)
    assert "<EMAIL_" in r.text
    assert "<PHONE_" in r.text
    assert "<SECRET_" in r.text
    assert "a@b.com" not in r.text
    assert "sk-" not in r.text


def test_llm_metadata_rejects_untrusted_strings_and_sensitive_keys():
    from core.llm.redaction import safe_metadata
    secret = "sk-" + "THISISASECRET123456789"
    assert safe_metadata({"context_tokens": 12, "trace_id": secret, "tenant_id": "other", "authorization": secret}) == {"context_tokens": 12}
    for value in (True, -1, 10_000_001, "12", 1.5, None):
        assert safe_metadata({"context_tokens": value, "secret": secret}) == {}
