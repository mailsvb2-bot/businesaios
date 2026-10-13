"""Strict advertising media acceptance before canonical governed publication.

Absorbs ClientPlatform's media asset shape without importing its SQL store,
provider client, payment owner or scheduler. This contract is evidence only:
a ready provider reference never authorizes publication or bypasses Policy.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

CANON_PHASE18_AD_PUBLICATION_ASSET_CONTRACT = True
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SAFE_ERROR = re.compile(r"[a-z0-9_.:-]{1,120}")
_MIME = {
    "image": {"image/jpeg", "image/png", "image/webp"},
    "video": {"video/mp4", "video/webm", "video/quicktime"},
}


class AdAssetKind(StrEnum):
    IMAGE = "image"
    VIDEO = "video"


class AdAssetSource(StrEnum):
    UPLOAD = "upload"
    GENERATED = "generated"


class AdAssetState(StrEnum):
    UPLOADING = "uploading"
    READY = "ready"
    AMBIGUOUS = "ambiguous"
    FAILED = "failed"


def _scope(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 240:
        raise ValueError(f"ad_asset_{name}_required")
    if any(ord(char) < 32 for char in value):
        raise ValueError(f"ad_asset_{name}_invalid")
    return value.strip()


@dataclass(frozen=True, slots=True)
class AdPublicationAssetEvidence:
    tenant_id: str
    business_id: str
    publication_job_id: str
    asset_id: str
    kind: AdAssetKind
    source: AdAssetSource
    content_type: str
    sha256: str
    size_bytes: int
    state: AdAssetState
    provider_image_hash: str | None = None
    provider_video_id: str | None = None
    provider_creative_id: str | None = None
    provider_error_code: str | None = None
    duration_seconds: int | None = None

    def __post_init__(self) -> None:
        for field in ("tenant_id", "business_id", "publication_job_id", "asset_id"):
            object.__setattr__(self, field, _scope(field, getattr(self, field)))
        kind = AdAssetKind(self.kind)
        state = AdAssetState(self.state)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "source", AdAssetSource(self.source))
        object.__setattr__(self, "state", state)
        mime = str(self.content_type).strip().lower()
        if mime not in _MIME[kind.value]:
            raise ValueError("ad_asset_content_type_unsupported")
        object.__setattr__(self, "content_type", mime)
        digest = str(self.sha256 or "").lower().strip()
        if not _SHA256.fullmatch(digest):
            raise ValueError("ad_asset_sha256_invalid")
        object.__setattr__(self, "sha256", digest)
        if type(self.size_bytes) is not int or not 0 < self.size_bytes <= 100_000_000:
            raise ValueError("ad_asset_size_invalid")
        if kind is AdAssetKind.IMAGE and self.size_bytes > 20_000_000:
            raise ValueError("ad_asset_image_too_large")
        if self.duration_seconds is not None and (
            kind is not AdAssetKind.VIDEO or type(self.duration_seconds) is not int
            or not 0 < self.duration_seconds <= 3600
        ):
            raise ValueError("ad_asset_duration_invalid")
        for field in ("provider_image_hash", "provider_video_id", "provider_creative_id"):
            value = getattr(self, field)
            if value is not None:
                object.__setattr__(self, field, _scope(field, value))
        if self.provider_error_code is not None:
            code = str(self.provider_error_code).strip().lower()
            if not _SAFE_ERROR.fullmatch(code):
                raise ValueError("ad_asset_provider_error_unsafe")
            object.__setattr__(self, "provider_error_code", code)
        if state is AdAssetState.READY:
            if kind is AdAssetKind.IMAGE and not self.provider_image_hash:
                raise ValueError("ad_asset_image_provider_proof_missing")
            if kind is AdAssetKind.VIDEO and not self.provider_video_id:
                raise ValueError("ad_asset_video_provider_proof_missing")
            if self.provider_error_code:
                raise ValueError("ad_asset_ready_with_provider_error")
        if state is AdAssetState.AMBIGUOUS and not self.provider_error_code:
            raise ValueError("ad_asset_ambiguity_requires_evidence")

    @property
    def eligible_for_publication_review(self) -> bool:
        """Only review eligibility; never an Execution/Policy approval."""
        return self.state is AdAssetState.READY


def require_scoped_asset_review(
    asset: AdPublicationAssetEvidence, *,
    tenant_id: str, business_id: str, publication_job_id: str,
) -> AdPublicationAssetEvidence:
    if type(asset) is not AdPublicationAssetEvidence:
        raise TypeError("ad_asset_evidence_required")
    if (asset.tenant_id != _scope("tenant_id", tenant_id)
            or asset.business_id != _scope("business_id", business_id)
            or asset.publication_job_id != _scope("publication_job_id", publication_job_id)):
        raise PermissionError("ad_asset_scope_conflict")
    if not asset.eligible_for_publication_review:
        raise RuntimeError("ad_asset_not_ready_for_review")
    return asset
