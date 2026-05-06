from __future__ import annotations

from security.payload_redaction import PayloadRedactor
from security.pii_redaction_policy import PIIRedactionPolicy


def test_pii_redaction_masks_common_identifiers_in_free_text() -> None:
    policy = PIIRedactionPolicy(replacement='[masked]')
    text = (
        'Contact alice@example.com or +31 6 1234 5678. '
        'Card 4111 1111 1111 1111, IP 192.168.1.10, IBAN NL91ABNA0417164300.'
    )

    redacted = policy.redact_text(text)

    assert 'alice@example.com' not in redacted
    assert '+31 6 1234 5678' not in redacted
    assert '4111 1111 1111 1111' not in redacted
    assert '192.168.1.10' not in redacted
    assert 'NL91ABNA0417164300' not in redacted
    assert redacted.count('[masked]') >= 5


def test_payload_redactor_redacts_sensitive_keys_and_nested_pii() -> None:
    redactor = PayloadRedactor()
    payload = {
        'tenant_id': 'tenant-a',
        'authorization': 'Bearer secret-value',
        'customer': {
            'email': 'alice@example.com',
            'phone': '+1 (555) 123-4567',
        },
        'notes': ['reachable at bob@example.com'],
    }

    redacted = redactor.redact(payload)

    assert redacted['authorization'] == '***REDACTED***'
    assert 'alice@example.com' not in redacted['customer']['email']
    assert '555' not in redacted['customer']['phone']
    assert 'bob@example.com' not in redacted['notes'][0]


def test_payload_redactor_truncates_overlong_strings_after_redaction() -> None:
    redactor = PayloadRedactor(max_string_length=16)
    payload = {'notes': 'user alice@example.com ' + ('x' * 100)}

    redacted = redactor.redact(payload)

    assert len(redacted['notes']) <= 17
    assert redacted['notes'].endswith('…')
    assert 'alice@example.com' not in redacted['notes']


def test_payload_redactor_stops_recursive_explosion_fail_closed() -> None:
    redactor = PayloadRedactor(max_depth=2)
    payload = {'a': {'b': {'c': {'email': 'alice@example.com'}}}}

    redacted = redactor.redact(payload)

    assert redacted['a']['b']['c'] == '<max-depth-redacted>'
