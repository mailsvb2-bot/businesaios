from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Mapping

from security.key_management_contract import KeyPurpose
from security.key_provider import KeyProvider


CANON_WEBHOOK_SIGNATURE_VERIFIER = True
WEBHOOK_SIGNATURE_VERSION = "v2"


@dataclass(frozen=True)
class WebhookVerificationResult:
    verified: bool
    reason: str
    key_id: str | None = None
    content_digest: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)


class WebhookSignatureVerifier:
    """Verify a tenant- and connector-bound replay-resistant webhook signature."""

    def __init__(
        self,
        *,
        key_provider: KeyProvider,
        header_name: str = "X-Signature",
        algorithm: str = "hmac-sha256",
        key_id_header_name: str = "X-Key-Id",
        timestamp_header_name: str = "X-Signature-Timestamp",
        nonce_header_name: str = "X-Signature-Nonce",
        version_header_name: str = "X-Signature-Version",
        max_age_seconds: int = 300,
        allow_future_skew_seconds: int = 30,
        require_timestamp: bool = True,
        require_nonce: bool = True,
    ) -> None:
        self._key_provider = key_provider
        self._header_name = str(header_name)
        self._algorithm = str(algorithm)
        self._key_id_header_name = str(key_id_header_name)
        self._timestamp_header_name = str(timestamp_header_name)
        self._nonce_header_name = str(nonce_header_name)
        self._version_header_name = str(version_header_name)
        self._max_age_seconds = int(max_age_seconds)
        self._allow_future_skew_seconds = int(allow_future_skew_seconds)
        self._require_timestamp = bool(require_timestamp)
        self._require_nonce = bool(require_nonce)

    def verify(
        self,
        *,
        headers: Mapping[str, str],
        body: bytes,
        tenant_id: str | None = None,
        connector_id: str | None = None,
        now: datetime | None = None,
    ) -> WebhookVerificationResult:
        tenant = str(tenant_id or "").strip()
        connector = str(connector_id or "").strip()
        if not tenant:
            return WebhookVerificationResult(verified=False, reason="tenant_id_required")
        if not connector:
            return WebhookVerificationResult(verified=False, reason="connector_id_required")

        signature = self._find_header(headers, self._header_name)
        if not signature:
            return WebhookVerificationResult(verified=False, reason="missing_signature")

        version = self._find_header(headers, self._version_header_name) or WEBHOOK_SIGNATURE_VERSION
        if version != WEBHOOK_SIGNATURE_VERSION:
            return WebhookVerificationResult(verified=False, reason="unsupported_signature_version")

        timestamp_raw = self._find_header(headers, self._timestamp_header_name)
        parsed_timestamp = self._parse_timestamp(timestamp_raw) if timestamp_raw else None
        if self._require_timestamp and parsed_timestamp is None:
            return WebhookVerificationResult(verified=False, reason="missing_or_invalid_timestamp")

        nonce = str(self._find_header(headers, self._nonce_header_name) or "").strip()
        if self._require_nonce and not nonce:
            return WebhookVerificationResult(verified=False, reason="missing_nonce")
        if len(nonce) < 16 or len(nonce) > 256:
            return WebhookVerificationResult(verified=False, reason="invalid_nonce")

        moment = now or datetime.now(timezone.utc)
        if moment.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        if parsed_timestamp is not None:
            if parsed_timestamp > moment + timedelta(seconds=self._allow_future_skew_seconds):
                return WebhookVerificationResult(verified=False, reason="timestamp_in_future")
            if moment - parsed_timestamp > timedelta(seconds=self._max_age_seconds):
                return WebhookVerificationResult(verified=False, reason="signature_too_old")

        key_id = self._find_header(headers, self._key_id_header_name)
        try:
            if key_id:
                key = self._key_provider.get(str(key_id))
                if key.tenant_id != tenant or key.connector_id != connector:
                    return WebhookVerificationResult(
                        verified=False,
                        reason="key_scope_mismatch",
                        key_id=key.key_id,
                    )
            else:
                key = self._key_provider.get_active_for(
                    purpose=KeyPurpose.WEBHOOK_VERIFICATION,
                    tenant_id=tenant,
                    connector_id=connector,
                    at=parsed_timestamp or moment,
                )
        except KeyError:
            return WebhookVerificationResult(verified=False, reason="missing_key")

        if key.purpose is not KeyPurpose.WEBHOOK_VERIFICATION:
            return WebhookVerificationResult(verified=False, reason="wrong_key_purpose", key_id=key.key_id)
        if not key.is_usable(at=parsed_timestamp or moment):
            return WebhookVerificationResult(verified=False, reason="key_not_usable", key_id=key.key_id)

        content_digest = hashlib.sha256(bytes(body)).hexdigest()
        signing_payload = self.build_signing_payload(
            timestamp=str(timestamp_raw or ""),
            nonce=nonce,
            tenant_id=tenant,
            connector_id=connector,
            content_digest=content_digest,
            version=version,
        )
        expected = base64.b64encode(
            hmac.new(key.secret_bytes, signing_payload, hashlib.sha256).digest()
        ).decode("ascii")
        metadata = {
            "algorithm": self._algorithm,
            "header_name": self._header_name,
            "version": version,
            "timestamp": str(timestamp_raw or ""),
            "nonce": nonce,
            "tenant_id": tenant,
            "connector_id": connector,
        }
        if not hmac.compare_digest(expected, str(signature)):
            return WebhookVerificationResult(
                verified=False,
                reason="bad_signature",
                key_id=key.key_id,
                content_digest=content_digest,
                metadata=metadata,
            )
        return WebhookVerificationResult(
            verified=True,
            reason="verified",
            key_id=key.key_id,
            content_digest=content_digest,
            metadata=metadata,
        )

    @staticmethod
    def build_signing_payload(
        *,
        timestamp: str,
        nonce: str,
        tenant_id: str,
        connector_id: str,
        content_digest: str,
        version: str = WEBHOOK_SIGNATURE_VERSION,
    ) -> bytes:
        fields = (
            str(version),
            str(timestamp),
            str(nonce),
            str(tenant_id),
            str(connector_id),
            str(content_digest),
        )
        if any("\n" in item or "\r" in item for item in fields):
            raise ValueError("webhook signing fields must be single-line")
        return ("\n".join(fields) + "\n").encode("utf-8")

    @staticmethod
    def _find_header(headers: Mapping[str, str], name: str) -> str | None:
        target = str(name).lower()
        for key, value in headers.items():
            if str(key).lower() == target:
                text = str(value).strip()
                return text or None
        return None

    @staticmethod
    def _parse_timestamp(value: str) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)


__all__ = [
    "CANON_WEBHOOK_SIGNATURE_VERIFIER",
    "WEBHOOK_SIGNATURE_VERSION",
    "WebhookSignatureVerifier",
    "WebhookVerificationResult",
]
