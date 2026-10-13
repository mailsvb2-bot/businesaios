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


@pytest.mark.asyncio
async def test_verified_provider_requires_one_durable_claim_and_matching_readback(monkeypatch):
    from interfaces.ads import registry
    monkeypatch.setitem(registry.CONNECTORS, "yandex_direct", {
        **registry.CONNECTORS["yandex_direct"],
        "implemented": True, "write": True, "verify": True, "production_ready": True,
    })

    class Gateway:
        def __init__(self):
            self.sent = []

        async def apply_plan(self, payload):
            self.sent.append(payload)
            return {"status": "ok", "results": [{"object_id": "provider-ad-1"}]}

    gateway = Gateway()
    claims = set()

    def approve(**kwargs):
        return kwargs["approval_reference"] == "approved-a" and kwargs["asset"].sha256 == "a" * 64

    def reserve_execution(**kwargs):
        key = kwargs["execution_reference"]
        if key in claims:
            return "already_claimed"
        claims.add(key)
        return "claimed"

    def verify_provider(**kwargs):
        return {"verified": True, "object_id": kwargs["object_id"]}

    call = dict(
        gateway=gateway, request=request(),
        verify_approval=approve,
        reserve_execution=reserve_execution,
        verify_provider=verify_provider,
    )
    first = await submit_reviewed_ad_publication(**call)
    assert first["status"] == "verified"
    assert gateway.sent[0].plan["ops"][0]["payload"]["image"] == "media-hash-a"
    repeated = await submit_reviewed_ad_publication(**call)
    assert repeated["reason"] == "publication_execution_already_reserved"
    assert len(gateway.sent) == 1


@pytest.mark.asyncio
async def test_ambiguous_provider_response_blocks_retry_under_durable_claim(monkeypatch):
    from interfaces.ads import registry
    monkeypatch.setitem(registry.CONNECTORS, "yandex_direct", {
        **registry.CONNECTORS["yandex_direct"],
        "implemented": True, "write": True, "verify": True, "production_ready": True,
    })
    claims = set()
    writes = []

    class UncertainGateway:
        async def apply_plan(self, request):
            writes.append(request)
            return {"status": "ok", "results": [{"status": "accepted"}]}

    def claim(**kwargs):
        key = kwargs["execution_reference"]
        if key in claims:
            return "already_claimed"
        claims.add(key)
        return "claimed"

    args = dict(
        gateway=UncertainGateway(), request=request(),
        verify_approval=lambda **kwargs: True,
        reserve_execution=claim,
        verify_provider=lambda **kwargs: {"verified": True},
    )
    first = await submit_reviewed_ad_publication(**args)
    second = await submit_reviewed_ad_publication(**args)
    assert first["reason"] == "provider_acceptance_ambiguous"
    assert second["reason"] == "publication_execution_already_reserved"
    assert len(writes) == 1


@pytest.mark.asyncio
async def test_approval_rejected_before_reserving_or_sending(monkeypatch):
    from interfaces.ads import registry
    monkeypatch.setitem(registry.CONNECTORS, "yandex_direct", {
        **registry.CONNECTORS["yandex_direct"],
        "implemented": True, "write": True, "verify": True, "production_ready": True,
    })
    claim = Mock(side_effect=AssertionError("claim forbidden"))
    sent = Mock(side_effect=AssertionError("write forbidden"))
    result = await submit_reviewed_ad_publication(
        gateway=SimpleNamespace(apply_plan=sent), request=request(),
        verify_approval=lambda **kwargs: False,
        reserve_execution=claim, verify_provider=Mock(),
    )
    assert result["reason"] == "owner_approval_not_verified"
    claim.assert_not_called()
    sent.assert_not_called()
