import pytest

from core.llm.redaction import prepare_sales_ai_text, redact_text


def test_redact_email_phone_tokenlike():
    s = "email a@b.com phone +31 6 1234 5678 key sk-ABCDEF1234567890"
    r = redact_text(s)
    assert "<EMAIL_" in r.text
    assert "<PHONE_" in r.text
    assert "<SECRET_" in r.text
    assert "a@b.com" not in r.text
    assert "sk-" not in r.text


def test_sales_ai_redaction_covers_urls_handles_and_long_ids() -> None:
    prepared = prepare_sales_ai_text(
        "Пишите @customer, профиль https://example.com/u/123 и id 1234567890",
        data_mode="redacted",
    )
    assert prepared.redacted is True
    assert "@customer" not in prepared.text
    assert "https://example.com" not in prepared.text
    assert "1234567890" not in prepared.text
    assert "<HANDLE_" in prepared.text
    assert "<URL_" in prepared.text
    assert "<ID_" in prepared.text


def test_sales_ai_standard_mode_is_bounded_but_not_redacted() -> None:
    prepared = prepare_sales_ai_text(
        "user@example.com " + ("x" * 100),
        data_mode="standard",
        max_chars=24,
    )
    assert prepared.redacted is False
    assert len(prepared.text) == 24
    assert "user@example.com" in prepared.text


def test_sales_ai_no_cloud_fails_before_egress() -> None:
    with pytest.raises(PermissionError, match="sales_ai_no_cloud"):
        prepare_sales_ai_text("hello", data_mode="no_cloud")
