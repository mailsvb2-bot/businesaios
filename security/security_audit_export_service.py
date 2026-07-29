from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Mapping

from security.external_audit_notarization import NotarizationReceipt


CANON_SECURITY_AUDIT_EXPORT_SERVICE = True


class SecurityAuditExportService:
    """Canonical owner of redacted + signed + verifiable security audit export."""

    def __init__(
        self,
        *,
        redaction_policy,
        signer,
        verifier,
        notarization_provider=None,
    ) -> None:
        self._redaction = redaction_policy
        self._signer = signer
        self._verifier = verifier
        self._notarization_provider = notarization_provider

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
        bundle_without_receipt = {
            'signed_payload': signed_payload,
            'certification': dict(certification or {}),
        }
        if self._notarization_provider is not None:
            notarized = self._notarization_provider.notarize(
                bundle=bundle_without_receipt,
                credential_ref=credential_ref,
            )
            ledger_anchor = str(notarized.ledger_anchor_id or '')
            receipt = {
                'notary_provider': notarized.provider_name,
                'receipt_id': notarized.receipt_id,
                'timestamp_epoch_s': notarized.notarized_at_epoch_s,
                'timestamp_token': notarized.timestamp_token,
                'ledger_anchor': ledger_anchor,
                'ledger_anchor_id': ledger_anchor,
                'payload_hash': notarized.payload_digest,
                'credential_ref': str(credential_ref or ''),
            }
        else:
            ts = int(time.time())
            ledger_anchor = f'ledger::{payload_hash}'
            receipt = {
                'notary_provider': 'local-notary',
                'timestamp_epoch_s': ts,
                'timestamp_token': f'tsa::{ts}::{payload_hash[:16]}',
                'ledger_anchor': ledger_anchor,
                'ledger_anchor_id': ledger_anchor,
                'payload_hash': payload_hash,
                'credential_ref': str(credential_ref or ''),
            }
        bundle = {**bundle_without_receipt, 'notarization_receipt': receipt}
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
        if self._notarization_provider is not None:
            try:
                notarized = NotarizationReceipt(
                    provider_name=str(receipt['notary_provider']),
                    receipt_id=str(receipt['receipt_id']),
                    payload_digest=str(receipt['payload_hash']),
                    notarized_at_epoch_s=int(receipt['timestamp_epoch_s']),
                    timestamp_token=(
                        None if receipt.get('timestamp_token') is None else str(receipt['timestamp_token'])
                    ),
                    ledger_anchor_id=(
                        None
                        if not (receipt.get('ledger_anchor_id') or receipt.get('ledger_anchor'))
                        else str(receipt.get('ledger_anchor_id') or receipt.get('ledger_anchor'))
                    ),
                )
            except (KeyError, TypeError, ValueError):
                return False
            return bool(
                self._notarization_provider.verify_receipt(
                    bundle={
                        'signed_payload': signed_payload,
                        'certification': dict(bundle.get('certification') or {}),
                    },
                    receipt=notarized,
                )
            )
        payload_hash = self._canonical_hash(dict(signed_payload.get('payload') or {}))
        anchor = str(receipt.get('ledger_anchor_id') or receipt.get('ledger_anchor') or '')
        return str(receipt.get('payload_hash') or '') == payload_hash and anchor.endswith(payload_hash)
