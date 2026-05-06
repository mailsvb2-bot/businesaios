from core.llm.redaction import redact_text


def test_redact_email_phone_tokenlike():
    s = "email a@b.com phone +31 6 1234 5678 key sk-ABCDEF1234567890"
    r = redact_text(s)
    assert "<EMAIL_" in r.text
    assert "<PHONE_" in r.text
    assert "<SECRET_" in r.text
    assert "a@b.com" not in r.text
    assert "sk-" not in r.text
