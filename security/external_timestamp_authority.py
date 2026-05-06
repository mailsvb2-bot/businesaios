from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

CANON_EXTERNAL_TIMESTAMP_AUTHORITY = True

@dataclass(frozen=True)
class TimestampAuthorityReceipt:
    authority_name: str
    timestamp_token: str
    signed_at_epoch_s: int


class ExternalTimestampAuthority:
    def __init__(self, *, authority_name: str, stamp_fn: Callable[..., dict], verify_fn: Callable[..., bool]) -> None:
        self._authority_name = str(authority_name)
        self._stamp_fn = stamp_fn
        self._verify_fn = verify_fn

    def stamp(self, *, payload_digest: str, credential_ref: str | None = None) -> TimestampAuthorityReceipt:
        response = dict(self._stamp_fn(authority_name=self._authority_name, payload_digest=str(payload_digest), credential_ref=credential_ref))
        return TimestampAuthorityReceipt(authority_name=self._authority_name, timestamp_token=str(response['timestamp_token']), signed_at_epoch_s=int(response['signed_at_epoch_s']))

    def verify(self, *, payload_digest: str, receipt: TimestampAuthorityReceipt) -> bool:
        return bool(self._verify_fn(authority_name=self._authority_name, payload_digest=str(payload_digest), timestamp_token=receipt.timestamp_token, signed_at_epoch_s=receipt.signed_at_epoch_s))

__all__ = ['CANON_EXTERNAL_TIMESTAMP_AUTHORITY', 'ExternalTimestampAuthority', 'TimestampAuthorityReceipt']
