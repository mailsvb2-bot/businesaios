from __future__ import annotations

from typing import Any, Mapping


CANON_SECURITY_AUDIT_EXPORT_SERVICE = True


class SecurityAuditExportService:
    """Canonical owner of redacted + signed + verifiable security audit export."""

    def __init__(
        self,
        *,
        redaction_policy,
        signer,
        verifier,
    ) -> None:
        self._redaction = redaction_policy
        self._signer = signer
        self._verifier = verifier

    def export_payload(self, *, payload: Mapping[str, Any]) -> dict[str, object]:
        candidate = {'payload': dict(payload)}
        if hasattr(self._redaction, 'redact_event_dict'):
            redacted = self._redaction.redact_event_dict(candidate).get('payload', {})
        else:
            redacted = dict(payload)
        return self._signer.sign_payload(payload=redacted)

    def verify_export(self, *, signed_payload: Mapping[str, Any]) -> bool:
        payload = dict(signed_payload.get('payload') or {})
        signature = str(signed_payload.get('signature') or '')
        return self._verifier.verify(payload=payload, signature=signature)
