from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from security.key_provider import KeyProvider
from security.key_management_contract import KeyMaterialRecord, KeyPurpose


CANON_REQUEST_SIGNING = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


@dataclass(frozen=True)
class SignedRequestEnvelope:
    key_id: str
    algorithm: str
    signature: str
    signed_at: datetime = field(default_factory=utc_now)
    content_digest: str = ''
    nonce: str = ''

    def validate(self) -> None:
        if not str(self.key_id or '').strip():
            raise ValueError('key_id is required')
        if not str(self.algorithm or '').strip():
            raise ValueError('algorithm is required')
        if not str(self.signature or '').strip():
            raise ValueError('signature is required')
        if not str(self.content_digest or '').strip():
            raise ValueError('content_digest is required')
        if self.signed_at.tzinfo is None:
            raise ValueError('signed_at must be timezone-aware')


class RequestSigner:
    algorithm = 'hmac-sha256:v2'

    def __init__(
        self,
        *,
        key_provider: KeyProvider,
        max_age_seconds: int = 300,
        allow_future_skew_seconds: int = 30,
    ) -> None:
        self._key_provider = key_provider
        self._max_age_seconds = int(max_age_seconds)
        self._allow_future_skew_seconds = int(allow_future_skew_seconds)

    def sign(self, *, payload: Mapping[str, Any], tenant_id: str | None = None, connector_id: str | None = None) -> SignedRequestEnvelope:
        key = self._resolve_key(tenant_id=tenant_id, connector_id=connector_id)
        content = _canonical_json_bytes(payload)
        signed_at = utc_now()
        nonce = secrets.token_urlsafe(12)
        digest = hashlib.sha256(content).hexdigest()
        to_sign = self._signature_input(
            key_id=key.key_id,
            signed_at=signed_at,
            nonce=nonce,
            content_digest=digest,
        )
        signature = base64.b64encode(hmac.new(key.secret_bytes, to_sign, hashlib.sha256).digest()).decode('ascii')
        return SignedRequestEnvelope(
            key_id=key.key_id,
            algorithm=self.algorithm,
            signature=signature,
            signed_at=signed_at,
            content_digest=digest,
            nonce=nonce,
        )

    def verify(self, *, payload: Mapping[str, Any], envelope: SignedRequestEnvelope, now: datetime | None = None) -> bool:
        envelope.validate()
        if envelope.algorithm not in {'hmac-sha256:v1', self.algorithm}:
            return False
        moment = now or utc_now()
        if moment.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        if envelope.signed_at > moment + timedelta(seconds=self._allow_future_skew_seconds):
            return False
        if moment - envelope.signed_at > timedelta(seconds=self._max_age_seconds):
            return False
        key = self._key_provider.get(envelope.key_id)
        if key.purpose is not KeyPurpose.REQUEST_SIGNING:
            return False
        if not key.is_usable(at=envelope.signed_at):
            return False
        content = _canonical_json_bytes(payload)
        digest = hashlib.sha256(content).hexdigest()
        if not hmac.compare_digest(digest, envelope.content_digest):
            return False
        if envelope.algorithm == 'hmac-sha256:v1':
            expected = base64.b64encode(hmac.new(key.secret_bytes, content, hashlib.sha256).digest()).decode('ascii')
            return hmac.compare_digest(expected, envelope.signature)
        expected = base64.b64encode(
            hmac.new(
                key.secret_bytes,
                self._signature_input(
                    key_id=envelope.key_id,
                    signed_at=envelope.signed_at,
                    nonce=envelope.nonce,
                    content_digest=envelope.content_digest,
                ),
                hashlib.sha256,
            ).digest()
        ).decode('ascii')
        return hmac.compare_digest(expected, envelope.signature)

    def _resolve_key(self, *, tenant_id: str | None, connector_id: str | None) -> KeyMaterialRecord:
        try:
            return self._key_provider.get_active_for(
                purpose=KeyPurpose.REQUEST_SIGNING,
                tenant_id=tenant_id,
                connector_id=connector_id,
            )
        except KeyError:
            return self._key_provider.issue_key(
                key_id=f'request-signing-{tenant_id or "global"}-{connector_id or "shared"}-v1',
                purpose=KeyPurpose.REQUEST_SIGNING,
                tenant_id=tenant_id,
                connector_id=connector_id,
            )

    @staticmethod
    def _signature_input(*, key_id: str, signed_at: datetime, nonce: str, content_digest: str) -> bytes:
        return '|'.join([
            str(key_id),
            signed_at.astimezone(timezone.utc).isoformat(),
            str(nonce),
            str(content_digest),
        ]).encode('utf-8')


__all__ = [
    'CANON_REQUEST_SIGNING',
    'RequestSigner',
    'SignedRequestEnvelope',
]
