"""A media contract cannot create a live ad without approved write + provider proof."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from bootstrap.ads_write_gateway import ReviewedAdPublication, submit_reviewed_ad_publication
from contracts.ad_publication_asset import AdAssetKind, AdAssetSource, AdAssetState, AdPublicationAssetEvidence


def request(**changes):
    asset = AdPublicationAssetEvidence(
        tenant_id="tenant-a", business_id="business-a",
        publication_job_id="job-a", asset_id="asset-a",
        kind=AdAssetKind.IMAGE, source=AdAssetSource.UPLOAD,
        content_type="image/jpeg", sha256="a" * 64,
        size_bytes=1024, state=AdAssetState.READY,
        provider_image_hash="media-hash-a",
    )
    values = dict(
        tenant_id="tenant-a", business_id="business-a",
        publication_job_id="job-a", platform="yandex_direct",
        account_id="account-a", object_type="ad",
        payload={"name": "Ad", "image": "media-hash-a"},
        asset=asset, approval_reference="approved-a", execution_reference="execution-a",
    )
    values.update(changes)
    return ReviewedAdPublication(**values)


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["yandex_direct", "google_ads", "tiktok_ads", "meta_ads"])
async def test_unproven_connector_cannot_publish_or_spend(platform):
    gateway = SimpleNamespace(apply_plan=Mock(side_effect=AssertionError("network forbidden")))
    result = await submit_reviewed_ad_publication(
        gateway=gateway, request=request(platform=platform),
        verify_approval=Mock(side_effect=AssertionError("should not approve")),
        reserve_execution=Mock(side_effect=AssertionError("should not reserve")),
        verify_provider=Mock(side_effect=AssertionError("should not verify")),
    )
    assert result["status"] == "blocked"
    assert result["reason"] == "provider_write_and_verification_unavailable"
    gateway.apply_plan.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_provider_is_denied():
    assert (await submit_reviewed_ad_publication(
        gateway=SimpleNamespace(), request=request(platform="fictional_provider"),
        verify_approval=None, reserve_execution=None, verify_provider=None,
    ))["reason"] == "unknown_ads_provider"


@pytest.mark.asyncio
async def test_missing_scope_cannot_be_admitted():
    assert (await submit_reviewed_ad_publication(
        gateway=SimpleNamespace(), request=request(tenant_id=""),
        verify_approval=None, reserve_execution=None, verify_provider=None,
    ))["reason"] == "scope_missing"


def test_media_scope_violation_never_changes_asset_provenance():
    row = request()
    with pytest.raises(PermissionError):
        from contracts.ad_publication_asset import require_scoped_asset_review
        require_scoped_asset_review(
            replace(row.asset, business_id="business-other"),
            tenant_id="tenant-a", business_id="business-a",
            publication_job_id="job-a",
        )
