from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from security.request_signing import RequestSigner, SignedRequestEnvelope


CANON_API_REQUEST_SIGNING_POLICY = True
CANON_API_FINAL_OWNER = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class SignedRequestHeaders:
    key_id: str
    algorithm: str
    signature: str
    signed_at: str
    content_digest: str
    nonce: str

    def as_headers(self) -> dict[str, str]:
        return {
            'X-Signature-Key-Id': self.key_id,
            'X-Signature-Algorithm': self.algorithm,
            'X-Signature': self.signature,
            'X-Signature-Timestamp': self.signed_at,
            'X-Content-Digest': self.content_digest,
            'X-Nonce': self.nonce,
        }


class RequestSigningPolicy:
    def __init__(self, *, signer: RequestSigner, required: bool = False) -> None:
        self._signer = signer
        self._required = bool(required)

    def sign_headers(
        self,
        *,
        payload: Mapping[str, Any],
        tenant_id: str | None = None,
        connector_id: str | None = None,
    ) -> SignedRequestHeaders:
        envelope = self._signer.sign(payload=payload, tenant_id=tenant_id, connector_id=connector_id)
        return SignedRequestHeaders(
            key_id=envelope.key_id,
            algorithm=envelope.algorithm,
            signature=envelope.signature,
            signed_at=envelope.signed_at.astimezone(timezone.utc).isoformat(),
            content_digest=envelope.content_digest,
            nonce=envelope.nonce,
        )

    def verify_headers(
        self,
        *,
        payload: Mapping[str, Any],
        headers: Mapping[str, str] | None,
        now: datetime | None = None,
    ) -> tuple[bool, str]:
        normalized = {str(k).lower(): str(v) for k, v in dict(headers or {}).items()}
        signature_fields = {
            'x-signature', 'x-signature-key-id', 'x-signature-algorithm', 'x-signature-timestamp', 'x-content-digest', 'x-nonce'
        }
        has_any = any(name in normalized for name in signature_fields)
        if not has_any and not self._required:
            return True, 'not_required'
        missing = [name for name in ('x-signature', 'x-signature-key-id', 'x-signature-algorithm', 'x-signature-timestamp', 'x-content-digest', 'x-nonce') if name not in normalized]
        if missing:
            return False, 'missing_signature_headers'
        try:
            envelope = SignedRequestEnvelope(
                key_id=normalized.get('x-signature-key-id', ''),
                algorithm=normalized.get('x-signature-algorithm', ''),
                signature=normalized.get('x-signature', ''),
                signed_at=_parse_dt(normalized.get('x-signature-timestamp', '')),
                content_digest=normalized.get('x-content-digest', ''),
                nonce=normalized.get('x-nonce', ''),
            )
        except Exception:
            return False, 'malformed_signature_headers'
        ok = self._signer.verify(payload=payload, envelope=envelope, now=now or utc_now())
        return ok, 'verified' if ok else 'bad_request_signature'


def _parse_dt(value: str) -> datetime:
    text = str(value or '').strip()
    if not text:
        raise ValueError('missing timestamp')
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


__all__ = [
    'CANON_API_REQUEST_SIGNING_POLICY',
    'RequestSigningPolicy',
    'SignedRequestHeaders',
]
