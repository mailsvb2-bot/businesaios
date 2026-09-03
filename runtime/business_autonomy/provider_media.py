from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CANON_PROVIDER_MEDIA_PREPARATION = True


def _utc_now_text() -> str:
    return datetime.now(UTC).isoformat()


def provider_media_file_digest(path: str | Path) -> str:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()



def public_provider_media_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return an audit/control-plane-safe copy without local media paths or remote tokens."""
    public = dict(payload or {})
    raw_attachments = public.get("attachments")
    if isinstance(raw_attachments, list):
        safe_items: list[dict[str, Any]] = []
        for raw in raw_attachments:
            if not isinstance(raw, Mapping):
                continue
            item = {str(key): value for key, value in raw.items() if str(key) not in {"source", "path", "token", "remote_token"}}
            source = str(raw.get("source") or raw.get("path") or "").strip()
            if source:
                item["source_ref_digest"] = hashlib.sha256(source.encode("utf-8")).hexdigest()
            safe_items.append(item)
        public["attachments"] = safe_items
    if "attachment" in public and public.get("attachment") not in {None, ""}:
        public["attachment"] = "[redacted-provider-attachment]"
    return public

def _state_key(*, tenant_id: str, business_id: str, provider_key: str, job_id: str, media_type: str, source_digest: str) -> str:
    seed = "|".join(
        (
            str(tenant_id).strip(),
            str(business_id).strip(),
            str(provider_key).strip(),
            str(job_id).strip(),
            str(media_type).strip(),
            str(source_digest).strip(),
        )
    )
    return "provider-media:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PreparedProviderMedia:
    state_key: str
    provider_key: str
    media_type: str
    source_digest: str
    remote_token: str = field(repr=False)
    version: int = 0

    @property
    def ready(self) -> bool:
        return bool(self.remote_token)


class ProviderMediaPreparationCoordinator:
    def __init__(self, cas: Any, *, ttl_seconds: int = 86400) -> None:
        self._cas = cas
        self._ttl_seconds = max(60, int(ttl_seconds))

    def read(
        self,
        *,
        tenant_id: str,
        business_id: str,
        provider_key: str,
        job_id: str,
        media_type: str,
        source_digest: str,
    ) -> PreparedProviderMedia | None:
        key = _state_key(
            tenant_id=tenant_id,
            business_id=business_id,
            provider_key=provider_key,
            job_id=job_id,
            media_type=media_type,
            source_digest=source_digest,
        )
        raw = self._cas.read(key=key)
        if not isinstance(raw, dict) or str(raw.get("status") or "") != "prepared":
            return None
        token = str(raw.get("remote_token") or "").strip()
        if not token or str(raw.get("source_digest") or "") != str(source_digest):
            return None
        return PreparedProviderMedia(
            state_key=key,
            provider_key=str(provider_key),
            media_type=str(media_type),
            source_digest=str(source_digest),
            remote_token=token,
            version=int(raw.get("version") or 0),
        )

    def store_prepared(
        self,
        *,
        tenant_id: str,
        business_id: str,
        provider_key: str,
        job_id: str,
        media_type: str,
        source_digest: str,
        remote_token: str,
    ) -> PreparedProviderMedia:
        token = str(remote_token or "").strip()
        if not token:
            raise ValueError("prepared media token is required")
        key = _state_key(
            tenant_id=tenant_id,
            business_id=business_id,
            provider_key=provider_key,
            job_id=job_id,
            media_type=media_type,
            source_digest=source_digest,
        )
        payload = {
            "status": "prepared",
            "provider_key": str(provider_key),
            "media_type": str(media_type),
            "source_digest": str(source_digest),
            "remote_token": token,
            "prepared_at_utc": _utc_now_text(),
        }
        for _ in range(8):
            current = self._cas.read(key=key)
            if isinstance(current, dict) and str(current.get("status") or "") == "prepared":
                existing = self.read(
                    tenant_id=tenant_id,
                    business_id=business_id,
                    provider_key=provider_key,
                    job_id=job_id,
                    media_type=media_type,
                    source_digest=source_digest,
                )
                if existing is not None:
                    return existing
            if current is None:
                if self._cas.create_if_absent(key=key, payload=payload, ttl_seconds=self._ttl_seconds):
                    created = self.read(
                        tenant_id=tenant_id,
                        business_id=business_id,
                        provider_key=provider_key,
                        job_id=job_id,
                        media_type=media_type,
                        source_digest=source_digest,
                    )
                    assert created is not None
                    return created
                continue
            version = int(current.get("version") or 0)
            if self._cas.compare_and_swap(
                key=key,
                expected_version=version,
                payload=payload,
                ttl_seconds=self._ttl_seconds,
            ):
                updated = self.read(
                    tenant_id=tenant_id,
                    business_id=business_id,
                    provider_key=provider_key,
                    job_id=job_id,
                    media_type=media_type,
                    source_digest=source_digest,
                )
                assert updated is not None
                return updated
        raise RuntimeError("provider media preparation CAS conflict")

    def invalidate(self, prepared: PreparedProviderMedia) -> bool:
        current = self._cas.read(key=prepared.state_key)
        if not isinstance(current, dict) or int(current.get("version") or 0) != prepared.version:
            return False
        payload = {
            "status": "invalidated",
            "provider_key": prepared.provider_key,
            "media_type": prepared.media_type,
            "source_digest": prepared.source_digest,
            "remote_token": "",
            "invalidated_at_utc": _utc_now_text(),
        }
        return bool(
            self._cas.compare_and_swap(
                key=prepared.state_key,
                expected_version=prepared.version,
                payload=payload,
                ttl_seconds=self._ttl_seconds,
            )
        )


__all__ = [
    "CANON_PROVIDER_MEDIA_PREPARATION",
    "PreparedProviderMedia",
    "ProviderMediaPreparationCoordinator",
    "provider_media_file_digest",
    "public_provider_media_payload",
]
