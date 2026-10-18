"""Governed ad journey: owner approval -> durable claim -> provider add -> get."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from bootstrap.ads_write_gateway import ReviewedAdPublication, submit_reviewed_ad_publication
from contracts.ad_publication_asset import (
    AdAssetKind, AdAssetSource, AdAssetState, AdPublicationAssetEvidence,
)
from interfaces.ads.yandex_direct_governed_execution import (
    DirectPublicationBinding, GovernedYandexDirectConnector,
)


def bound():
    return DirectPublicationBinding(
        tenant_id="tenant", business_id="business", account_id="account",
        publication_job_id="publication", execution_reference="reservation",
        approval_reference="approval", campaign_id=7, ad_group_id=11,
        image_hash="hash-123", title="Консультация", description="Запись",
        destination_url="https://example.org/book")


def asset():
    return AdPublicationAssetEvidence(
        tenant_id="tenant", business_id="business", publication_job_id="publication",
        asset_id="adasset", kind=AdAssetKind.IMAGE, source=AdAssetSource.GENERATED,
        content_type="image/png", sha256="a" * 64, size_bytes=1024,
        state=AdAssetState.READY, provider_image_hash="hash-123")


def readback(*, state="ON", status="ACCEPTED", image="hash-123", campaign=7):
    return {"result": {"Ads": [{
        "Id": 109, "AdGroupId": 11, "CampaignId": campaign,
        "Type": "RESPONSIVE_AD", "Status": status, "State": state,
        "ResponsiveAd": {"AdImages": [{"AdImageHash": image}]},
    }]}}


def make_adapter(*, reply=None, provider=None):
    calls = []
    async def send(*, account_id, request):
        calls.append(("add", account_id, request))
        return reply if reply is not None else {"result": {"AddResults": [{"Id": 109}]}}
    async def read(*, account_id, request):
        calls.append(("get", account_id, request))
        return provider if provider is not None else readback()
    return GovernedYandexDirectConnector(binding=bound(), send=send, read=read), calls


@pytest.mark.asyncio
async def test_sealed_add_then_authoritative_get_never_infers_delivery_from_add():
    adapter, calls = make_adapter()
    approved = {"name": "Консультация", "text": "Запись",
                "href": "https://example.org/book", "image": "hash-123"}
    receipt = await adapter.create_or_update(
        tenant_id="tenant", account_id="account", object_type="ad", payload=approved)
    assert receipt == {"status": "accepted", "object_id": "109"}
    assert calls[0][2]["method"] == "add"
    assert len(calls) == 1
    proof = await adapter.verify_created_ad(
        tenant_id="tenant", business_id="business", platform="yandex_direct",
        account_id="account", publication_job_id="publication",
        object_id="109", asset=asset())
    assert proof == {"verified": True, "status": "provider_verified", "object_id": "109"}
    assert calls[1][2]["method"] == "get"
    assert calls[1][2]["params"]["SelectionCriteria"] == {"Ids": [109]}


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", [
    {"tenant_id": "other"}, {"account_id": "other"}, {"object_type": "campaign"},
    {"payload": {"name": "changed"}},
])
async def test_changed_owner_scope_or_approved_payload_never_calls_provider(changed):
    adapter, calls = make_adapter()
    args = dict(tenant_id="tenant", account_id="account", object_type="ad",
                payload={"name": "Консультация", "text": "Запись",
                         "href": "https://example.org/book", "image": "hash-123"})
    with pytest.raises(PermissionError):
        await adapter.create_or_update(**{**args, **changed})
    assert calls == []


@pytest.mark.asyncio
async def test_failed_and_ambiguous_provider_add_never_read_back():
    for failure in ({"error": {"code": 1}}, {"result": {"AddResults": []}},
                    {"result": {"AddResults": [{"Id": 109, "Warnings": [{"Code": 1}]}]}}):
        adapter, calls = make_adapter(reply=failure)
        with pytest.raises(RuntimeError):
            await adapter.create_or_update(
                tenant_id="tenant", account_id="account", object_type="ad",
                payload={"name": "Консультация", "text": "Запись",
                         "href": "https://example.org/book", "image": "hash-123"})
        assert [row[0] for row in calls] == ["add"]


@pytest.mark.asyncio
async def test_moderation_and_wrong_identity_fail_closed():
    adapter, calls = make_adapter(provider=readback(status="MODERATION"))
    result = await adapter.verify_created_ad(
        tenant_id="tenant", business_id="business", platform="yandex_direct",
        account_id="account", publication_job_id="publication", object_id="109", asset=asset())
    assert result["verified"] is False
    assert result["status"] == "pending"
    adapter, calls = make_adapter(provider=readback(campaign=9))
    with pytest.raises(PermissionError):
        await adapter.verify_created_ad(
            tenant_id="tenant", business_id="business", platform="yandex_direct",
            account_id="account", publication_job_id="publication", object_id="109", asset=asset())
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_asset_scope_fails_before_readback():
    adapter, calls = make_adapter()
    with pytest.raises(PermissionError):
        await adapter.verify_created_ad(
            tenant_id="tenant", business_id="business", platform="yandex_direct",
            account_id="account", publication_job_id="publication", object_id="109",
            asset=replace(asset(), provider_image_hash="attacker"))
    assert calls == []


@pytest.mark.asyncio
async def test_canonical_gateway_requires_owner_approval_and_durable_claim(monkeypatch):
    from interfaces.ads import registry
    adapter, calls = make_adapter()
    # Test-only capability override; never enabled in production registry.
    monkeypatch.setitem(registry.CONNECTORS, "yandex_direct", {
        **registry.CONNECTORS["yandex_direct"],
        "implemented": True, "write": True, "verify": True, "production_ready": True})
    class Gateway:
        async def apply_plan(self, req):
            op = req.plan["ops"][0]
            result = await adapter.create_or_update(
                tenant_id=req.tenant_id, account_id=op["account_id"],
                object_type=op["object_type"], payload=op["payload"])
            return {"status": "ok", "results": [result]}
    req = ReviewedAdPublication(
        tenant_id="tenant", business_id="business", publication_job_id="publication",
        platform="yandex_direct", account_id="account", object_type="ad",
        payload={"name": "Консультация", "text": "Запись",
                 "href": "https://example.org/book", "image": "hash-123"},
        asset=asset(), approval_reference="approval", execution_reference="reservation")
    claims = set()
    def reserve_execution(**kwargs):
        if kwargs["execution_reference"] in claims:
            return "already_claimed"
        claims.add(kwargs["execution_reference"])
        return "claimed"
    args = dict(gateway=Gateway(), request=req, reserve_execution=reserve_execution,
                verify_provider=adapter.verify_created_ad)
    # No approval: cannot write, reserve, or make external calls.
    denied = await submit_reviewed_ad_publication(
        **{**args, "verify_approval": lambda **kw: False})
    assert denied["reason"] == "owner_approval_not_verified"
    assert claims == set() and calls == []
    first = await submit_reviewed_ad_publication(
        **{**args, "verify_approval": lambda **kw: True})
    assert first["status"] == "verified"
    assert first["provider_object_id"] == "109"
    assert [x[0] for x in calls] == ["add", "get"]
    retry = await submit_reviewed_ad_publication(
        **{**args, "verify_approval": lambda **kw: True})
    assert retry["reason"] == "publication_execution_already_reserved"
    assert [x[0] for x in calls] == ["add", "get"]
