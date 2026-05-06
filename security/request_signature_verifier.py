from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from security.request_signing import RequestSigner, SignedRequestEnvelope


CANON_REQUEST_SIGNATURE_VERIFIER = True


@dataclass(frozen=True)
class RequestVerificationResult:
    valid: bool
    reason: str


class RequestSignatureVerifier:
    """Canonical verifier facade over RequestSigner.

    Keeps signature verification on one owner surface so callers do not need to
    know signer internals or duplicate verification logic.
    """

    def __init__(self, *, signer: RequestSigner) -> None:
        self._signer = signer

    def verify(
        self,
        *,
        payload: Mapping[str, Any],
        envelope: SignedRequestEnvelope,
        now: datetime | None = None,
    ) -> RequestVerificationResult:
        try:
            valid = self._signer.verify(payload=payload, envelope=envelope, now=now)
        except Exception as exc:
            return RequestVerificationResult(valid=False, reason=exc.__class__.__name__)
        return RequestVerificationResult(
            valid=bool(valid),
            reason='ok' if valid else 'signature_invalid',
        )


__all__ = [
    'CANON_REQUEST_SIGNATURE_VERIFIER',
    'RequestSignatureVerifier',
    'RequestVerificationResult',
]
