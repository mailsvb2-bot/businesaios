from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Mapping

from security.key_provider import KeyProvider
from security.key_management_contract import KeyPurpose


CANON_WEBHOOK_SIGNATURE_VERIFIER = True


@dataclass(frozen=True)
class WebhookVerificationResult:
    verified: bool
    reason: str
    key_id: str | None = None
    content_digest: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)


class WebhookSignatureVerifier:
    def __init__(
        self,
        *,
        key_provider: KeyProvider,
        header_name: str = 'X-Signature',
        algorithm: str = 'hmac-sha256',
        key_id_header_name: str = 'X-Key-Id',
        timestamp_header_name: str = 'X-Signature-Timestamp',
        max_age_seconds: int = 300,
        allow_future_skew_seconds: int = 30,
        require_timestamp: bool = False,
    ) -> None:
        self._key_provider = key_provider
        self._header_name = str(header_name)
        self._algorithm = str(algorithm)
        self._key_id_header_name = str(key_id_header_name)
        self._timestamp_header_name = str(timestamp_header_name)
        self._max_age_seconds = int(max_age_seconds)
        self._allow_future_skew_seconds = int(allow_future_skew_seconds)
        self._require_timestamp = bool(require_timestamp)

    def verify(
        self,
        *,
        headers: Mapping[str, str],
        body: bytes,
        tenant_id: str | None = None,
        connector_id: str | None = None,
        now: datetime | None = None,
    ) -> WebhookVerificationResult:
        signature = self._find_header(headers, self._header_name)
        if not signature:
            return WebhookVerificationResult(verified=False, reason='missing_signature')
        moment = now or datetime.now(timezone.utc)
        ts_raw = self._find_header(headers, self._timestamp_header_name)
        parsed_timestamp = self._parse_timestamp(ts_raw) if ts_raw else None
        if self._require_timestamp and parsed_timestamp is None:
            return WebhookVerificationResult(verified=False, reason='missing_timestamp')
        if parsed_timestamp is not None:
            if parsed_timestamp > moment + timedelta(seconds=self._allow_future_skew_seconds):
                return WebhookVerificationResult(verified=False, reason='timestamp_in_future')
            if moment - parsed_timestamp > timedelta(seconds=self._max_age_seconds):
                return WebhookVerificationResult(verified=False, reason='signature_too_old')
        key_id = self._find_header(headers, self._key_id_header_name)
        try:
            key = self._key_provider.get(str(key_id)) if key_id else self._key_provider.get_active_for(
                purpose=KeyPurpose.WEBHOOK_VERIFICATION,
                tenant_id=tenant_id,
                connector_id=connector_id,
                at=parsed_timestamp or moment,
            )
        except KeyError:
            return WebhookVerificationResult(verified=False, reason='missing_key')
        if key.purpose is not KeyPurpose.WEBHOOK_VERIFICATION:
            return WebhookVerificationResult(verified=False, reason='wrong_key_purpose', key_id=key.key_id)
        if not key.is_usable(at=parsed_timestamp or moment):
            return WebhookVerificationResult(verified=False, reason='key_not_usable', key_id=key.key_id)
        content_digest = hashlib.sha256(bytes(body)).hexdigest()
        expected = base64.b64encode(hmac.new(key.secret_bytes, bytes(body), hashlib.sha256).digest()).decode('ascii')
        if not hmac.compare_digest(expected, str(signature)):
            return WebhookVerificationResult(
                verified=False,
                reason='bad_signature',
                key_id=key.key_id,
                content_digest=content_digest,
                metadata={'algorithm': self._algorithm, 'header_name': self._header_name},
            )
        return WebhookVerificationResult(
            verified=True,
            reason='verified',
            key_id=key.key_id,
            content_digest=content_digest,
            metadata={'algorithm': self._algorithm, 'header_name': self._header_name},
        )

    @staticmethod
    def _find_header(headers: Mapping[str, str], name: str) -> str | None:
        target = str(name).lower()
        for key, value in headers.items():
            if str(key).lower() == target:
                return str(value)
        return None

    @staticmethod
    def _parse_timestamp(value: str) -> datetime | None:
        text = str(value or '').strip()
        if not text:
            return None
        if text.endswith('Z'):
            text = text[:-1] + '+00:00'
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed


__all__ = [
    'CANON_WEBHOOK_SIGNATURE_VERIFIER',
    'WebhookSignatureVerifier',
    'WebhookVerificationResult',
]
