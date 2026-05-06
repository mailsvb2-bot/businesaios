from compliance.pii_guard import PIIGuard


def test_pii_guard_detects_email() -> None:
    guard = PIIGuard()
    result = guard.inspect('Contact me at john.doe@example.com')
    assert result.contains_pii is True
    assert len(result.findings) >= 1


def test_pii_guard_redacts_email() -> None:
    guard = PIIGuard()
    text = 'Email: john.doe@example.com'
    result = guard.inspect(text)
    redacted = result.redact(text)
    assert 'john.doe@example.com' not in redacted
    assert '[REDACTED]' in redacted


def test_pii_guard_redacts_secret() -> None:
    guard = PIIGuard()
    text = 'api_key=supersecretvalue'
    result = guard.inspect(text)
    redacted = result.redact(text, replacement='[REDACTED_SECRET]')
    assert 'supersecretvalue' not in redacted
