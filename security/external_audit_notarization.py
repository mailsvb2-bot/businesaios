from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Mapping

from security.external_timestamp_authority import ExternalTimestampAuthority, TimestampAuthorityReceipt
from security.public_ledger_anchor import LedgerAnchorReceipt, PublicLedgerAnchor

CANON_EXTERNAL_AUDIT_NOTARIZATION = True

@dataclass(frozen=True)
class NotarizationReceipt:
    provider_name: str
    receipt_id: str
    payload_digest: str
    notarized_at_epoch_s: int
    timestamp_token: str | None = None
    ledger_anchor_id: str | None = None

class ExternalAuditNotarizationProvider:
    """Canonical owner for external-proof style notarization receipts."""
    def __init__(self, *, provider_name: str = 'local-notary', timestamp_authority: ExternalTimestampAuthority | None = None, ledger_anchor: PublicLedgerAnchor | None = None) -> None:
        self._provider_name = str(provider_name)
        self._timestamp_authority = timestamp_authority
        self._ledger_anchor = ledger_anchor

    def notarize(self, *, bundle: Mapping[str, Any], credential_ref: str | None = None) -> NotarizationReceipt:
        canonical = json.dumps(dict(bundle), ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        now = int(time.time())
        receipt_id = hashlib.sha256(f'{self._provider_name}|{digest}|{now}'.encode('utf-8')).hexdigest()
        timestamp_receipt = None if self._timestamp_authority is None else self._timestamp_authority.stamp(payload_digest=digest, credential_ref=credential_ref)
        ledger_receipt = None if self._ledger_anchor is None else self._ledger_anchor.anchor(payload_digest=digest, credential_ref=credential_ref)
        return NotarizationReceipt(provider_name=self._provider_name, receipt_id=receipt_id, payload_digest=digest, notarized_at_epoch_s=now, timestamp_token=None if timestamp_receipt is None else timestamp_receipt.timestamp_token, ledger_anchor_id=None if ledger_receipt is None else ledger_receipt.anchor_id)

    def verify_receipt(self, *, bundle: Mapping[str, Any], receipt: NotarizationReceipt) -> bool:
        canonical = json.dumps(dict(bundle), ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        if digest != receipt.payload_digest or str(receipt.provider_name) != self._provider_name:
            return False
        timestamp_ok = True
        if self._timestamp_authority is not None and receipt.timestamp_token is not None:
            timestamp_ok = self._timestamp_authority.verify(payload_digest=digest, receipt=TimestampAuthorityReceipt(authority_name=self._timestamp_authority._authority_name, timestamp_token=receipt.timestamp_token, signed_at_epoch_s=receipt.notarized_at_epoch_s))
        ledger_ok = True
        if self._ledger_anchor is not None and receipt.ledger_anchor_id is not None:
            ledger_ok = self._ledger_anchor.verify(payload_digest=digest, receipt=LedgerAnchorReceipt(ledger_name=self._ledger_anchor._ledger_name, anchor_id=receipt.ledger_anchor_id, anchored_digest=digest))
        return timestamp_ok and ledger_ok

__all__ = ['CANON_EXTERNAL_AUDIT_NOTARIZATION', 'ExternalAuditNotarizationProvider', 'NotarizationReceipt']
