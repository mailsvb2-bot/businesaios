from __future__ import annotations

from typing import Any, Mapping

from security.audit_redaction_policy import AuditRedactionPolicy
from security.payload_redaction import PayloadRedactor

_CANON_AUDIT_POLICY = AuditRedactionPolicy()
_CANON_PAYLOAD_REDACTOR = PayloadRedactor()


def redact_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Canonical low-level redaction adapter.

    Keeps the existing infrastructure.observability entrypoint stable while
    delegating actual secret/PII stripping to the shared security namespace.
    """
    payload = dict(data)
    if 'payload' in payload:
        return _CANON_AUDIT_POLICY.redact_event_dict(payload)
    redacted = _CANON_PAYLOAD_REDACTOR.redact(payload)
    if not isinstance(redacted, dict):
        return {'payload': redacted}
    return redacted
