"""End-to-end shape: reviewed image/video receipts enter the existing ads gateway."""
from __future__ import annotations

import pytest

from application.visual_creative_semantics.phase18_advertising_studio import (
    prepare_advertising_creatives,
)
from bootstrap.phase18_advertising_media_review import prepare_reviewed_generated_ad


@pytest.mark.parametrize("kind,mime,reference", [
    ("image", "image/png", "provider_image_hash"),
    ("video", "video/mp4", "provider_video_id"),
])
def test_reviewed_media_reuses_one_existing_publication_owner(kind, mime, reference):
    brief = prepare_advertising_creatives(
        tenant_id="t1", business_id="b1", campaign_id="c1",
        headline="Consultation", description="Book a meeting",
        brand_context="Brand blue", campaign_goal="Appointments",
        kind=kind, formats=("square",),
    )[0]
    receipt = {
        "tenant_id": "t1", "business_id": "b1",
        "creative_id": brief.creative_id,
        "approval_fingerprint": brief.approval_fingerprint,
        "kind": kind, "status": "succeeded", "sha256": "a" * 64,
        "content_type": mime, "size_bytes": 1024, reference: "provider-media-1",
    }
    def convert(r):
        return prepare_reviewed_generated_ad(
            brief=brief, approved_fingerprint=brief.approval_fingerprint,
            receipt=r, publication_job_id="job-1", platform="yandex_direct",
            account_id="account-1", approval_reference="approval-1",
            execution_reference="execution-1", destination_url="https://example.org/book",
        )
    prepared = convert(receipt)
    assert prepared.asset.source.value == "generated"
    assert prepared.asset.eligible_for_publication_review
    assert prepared.asset.kind.value == kind
    assert prepared.payload["image" if kind == "image" else "video"] == "provider-media-1"
    assert prepared.execution_reference == "execution-1"
    assert prepared.approval_reference == "approval-1"
    for change in ({"business_id": "other"}, {"status": "pending"},
                   {"sha256": "wrong"}, {reference: ""}):
        with pytest.raises((RuntimeError, ValueError)):
            convert({**receipt, **change})
