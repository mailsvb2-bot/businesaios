from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

CANON_PUBLIC_LEDGER_ANCHOR = True

@dataclass(frozen=True)
class LedgerAnchorReceipt:
    ledger_name: str
    anchor_id: str
    anchored_digest: str


class PublicLedgerAnchor:
    def __init__(self, *, ledger_name: str, anchor_fn: Callable[..., dict], verify_fn: Callable[..., bool]) -> None:
        self._ledger_name = str(ledger_name)
        self._anchor_fn = anchor_fn
        self._verify_fn = verify_fn

    def anchor(self, *, payload_digest: str, credential_ref: str | None = None) -> LedgerAnchorReceipt:
        response = dict(self._anchor_fn(ledger_name=self._ledger_name, payload_digest=str(payload_digest), credential_ref=credential_ref))
        return LedgerAnchorReceipt(ledger_name=self._ledger_name, anchor_id=str(response['anchor_id']), anchored_digest=str(response.get('anchored_digest') or payload_digest))

    def verify(self, *, payload_digest: str, receipt: LedgerAnchorReceipt) -> bool:
        return bool(self._verify_fn(ledger_name=self._ledger_name, payload_digest=str(payload_digest), anchor_id=receipt.anchor_id, anchored_digest=receipt.anchored_digest))

__all__ = ['CANON_PUBLIC_LEDGER_ANCHOR', 'PublicLedgerAnchor', 'LedgerAnchorReceipt']
