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


def test_payload_redactor_masks_embedded_credentials_without_key_hints() -> None:
    redactor = PayloadRedactor()
    secrets = (
        'Bearer abcdefghijklmnopqrstuvwxyz123456',
        '123456789:abcdefghijklmnopqrstuvwxyz123456',
        'sk-' + 'abcdefghijklmnopqrstuvwx',
        'password=very-private-secret',
        'Authorization: Basic abcdefghijklmnop',
        'Cookie: session=private-value; refresh=other-private-value',
        'client_secret="quoted-private-value"',
    )
    for raw in secrets:
        result = redactor.redact({'notes': 'diagnostic ' + raw})['notes']
        assert raw not in result
        assert '***REDACTED***' in result
    assert redactor.redact({'notes': 'ordinary diagnostic status'})['notes'] == 'ordinary diagnostic status'


def test_llm_redaction_uses_canonical_free_text_secret_patterns() -> None:
    from core.llm.redaction import redact_text

    secrets = (
        "Bearer eyJhbGciOiJIUzI1NiJ9.canarypayload.canarysig",
        "123456789:AAH-abcdefghijklmnopqrstuvwxyz0123456",
        "sk-abcdefghijklmnop1234",
        "AIzaSyDUMMYabcdefghijklmnopqrstuv",
        "live_AbCdEfGhIjKlMnOpQrStUv",
        "password=hunter2-canary",
    )
    result = redact_text(", ".join(secrets))
    assert all(secret not in result.text for secret in secrets)
    assert set(result.mapping.values()) == set(secrets)


def test_secrets_resolution_redacts_auth_and_cookie_fields_but_keeps_secret_refs() -> None:
    from config.secrets_resolution_policy import SecretsResolutionPolicy

    result = SecretsResolutionPolicy().redact_mapping({
        "headers": {
            "Authorization": "Bearer header-canary",
            "Cookie": "sid=cookie-canary",
            "Set-Cookie": "refresh=set-cookie-canary",
        },
        "token_ref": "secret://tenant-a/provider-token",
        "host": "api.example.test",
    })
    assert result["headers"] == {
        "Authorization": "[REDACTED]",
        "Cookie": "[REDACTED]",
        "Set-Cookie": "[REDACTED]",
    }
    assert result["token_ref"] == "secret://tenant-a/provider-token"
    assert result["host"] == "api.example.test"
