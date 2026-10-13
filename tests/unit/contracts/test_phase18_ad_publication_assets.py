from dataclasses import replace

import pytest

from contracts.ad_publication_asset import (
    AdAssetKind,
    AdAssetSource,
    AdAssetState,
    AdPublicationAssetEvidence,
    require_scoped_asset_review,
)


def asset(**changes):
    fields = dict(
        tenant_id="tenant-1", business_id="business-1",
        publication_job_id="job-1", asset_id="asset-1",
        kind=AdAssetKind.IMAGE, source=AdAssetSource.UPLOAD,
        content_type="image/jpeg", sha256="a" * 64,
        size_bytes=2000, state=AdAssetState.READY,
        provider_image_hash="provider-hash-1",
    )
    fields.update(changes)
    return AdPublicationAssetEvidence(**fields)


def test_donor_image_and_video_provider_evidence_is_scoped_before_review():
    image = asset()
    assert require_scoped_asset_review(
        image, tenant_id="tenant-1", business_id="business-1",
        publication_job_id="job-1",
    ) is image
    video = asset(
        kind=AdAssetKind.VIDEO, content_type="video/mp4",
        provider_image_hash=None, provider_video_id="video-provider-1",
        duration_seconds=20,
    )
    assert video.eligible_for_publication_review
    with pytest.raises(PermissionError):
        require_scoped_asset_review(
            image, tenant_id="tenant-1", business_id="business-2",
            publication_job_id="job-1",
        )


@pytest.mark.parametrize("changes", [
    {"sha256": "sha-not-valid"},
    {"size_bytes": -1},
    {"size_bytes": True},
    {"size_bytes": 100_000_001},
    {"content_type": "application/octet-stream"},
    {"content_type": "image/svg+xml"},
    {"provider_image_hash": None},
    {"provider_image_hash": "bad\nvalue"},
    {"provider_error_code": "bad\nheader"},
    {"provider_error_code": "provider_failed"},
    {"duration_seconds": 50},
    {"business_id": ""},
    {"tenant_id": "tenant\rspoof"},
    {"kind": AdAssetKind.VIDEO, "content_type": "video/mp4", "provider_image_hash": None},
    {"state": AdAssetState.AMBIGUOUS, "provider_image_hash": None},
])
def test_asset_rejects_spoofed_unbounded_or_untrusted_media(changes):
    with pytest.raises(ValueError):
        asset(**changes)


@pytest.mark.parametrize("state", [
    AdAssetState.UPLOADING, AdAssetState.FAILED,
])
def test_unconfirmed_upload_cannot_pass_publication_review(state):
    row = asset(state=state, provider_image_hash=None)
    assert row.eligible_for_publication_review is False
    with pytest.raises(RuntimeError):
        require_scoped_asset_review(
            row, tenant_id="tenant-1", business_id="business-1",
            publication_job_id="job-1",
        )


def test_ambiguous_upload_must_block_automatic_repeat_and_review():
    row = asset(
        state=AdAssetState.AMBIGUOUS, provider_image_hash=None,
        provider_error_code="provider_timeout_after_upload",
    )
    assert not row.eligible_for_publication_review
    with pytest.raises(RuntimeError):
        require_scoped_asset_review(
            row, tenant_id="tenant-1", business_id="business-1",
            publication_job_id="job-1",
        )
    assert replace(row, state=AdAssetState.FAILED).eligible_for_publication_review is False


def test_any_media_evidence_never_claims_provider_delivery_or_execution():
    assert not any(
        token in AdPublicationAssetEvidence.__dataclass_fields__
        for token in ("published", "executed", "invoice_id", "payment_confirmed")
    )
