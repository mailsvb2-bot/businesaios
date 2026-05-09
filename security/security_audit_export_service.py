from __future__ import annotations

import hashlib
import json
import time
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

    @staticmethod
    def _canonical_hash(payload: Mapping[str, Any]) -> str:
        canonical = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    def export_payload(self, *, payload: Mapping[str, Any]) -> dict[str, object]:
        candidate = {'payload': dict(payload)}
        if hasattr(self._redaction, 'redact_event_dict'):
            redacted = self._redaction.redact_event_dict(candidate).get('payload', {})
        else:
            redacted = dict(payload)
        return self._signer.sign_payload(payload=dict(redacted))

    def export_bundle(
        self,
        *,
        payload: Mapping[str, Any],
        certification: Mapping[str, Any] | None = None,
        credential_ref: str | None = None,
    ) -> dict[str, object]:
        signed_payload = self.export_payload(payload=payload)
        payload_hash = self._canonical_hash(dict(signed_payload.get('payload') or {}))
        ts = int(time.time())
        receipt = {
            'notary_provider': 'local-notary',
            'timestamp_epoch_s': ts,
            'timestamp_token': f'tsa::{ts}::{payload_hash[:16]}',
            'ledger_anchor': f'ledger::{payload_hash}',
            'payload_hash': payload_hash,
            'credential_ref': str(credential_ref or ''),
        }
        bundle = {
            'signed_payload': signed_payload,
            'certification': dict(certification or {}),
            'notarization_receipt': receipt,
        }
        return {'bundle': bundle, 'notarization_receipt': receipt}

    def verify_export(self, *, signed_payload: Mapping[str, Any]) -> bool:
        payload = dict(signed_payload.get('payload') or {})
        signature = str(signed_payload.get('signature') or '')
        return self._verifier.verify(payload=payload, signature=signature)

    def verify_bundle(self, *, exported_bundle: Mapping[str, Any]) -> bool:
        bundle = dict(exported_bundle.get('bundle') or {})
        signed_payload = dict(bundle.get('signed_payload') or {})
        receipt = dict(bundle.get('notarization_receipt') or exported_bundle.get('notarization_receipt') or {})
        if not self.verify_export(signed_payload=signed_payload):
            return False
        payload_hash = self._canonical_hash(dict(signed_payload.get('payload') or {}))
        anchor = str(receipt.get('ledger_anchor') or '')
        return str(receipt.get('payload_hash') or '') == payload_hash and anchor.endswith(payload_hash)
