"""End-to-end provider evidence contract against official Direct v5 envelope shape."""
from __future__ import annotations

from dataclasses import replace

import pytest

from interfaces.ads.yandex_direct_publication_proof import (
    DirectAdIdentity, parse_ads_add_receipt, prepare_ads_get,
    validate_publication_context, verify_ads_get,
)


def identity():
    return DirectAdIdentity(109, 11, 7, "hash-123", "https://shop.example.org")


def evidence(*, status="ACCEPTED", state="ON"):
    return {"result": {"Ads": [{"Id": 109, "CampaignId": 7,
        "AdGroupId": 11, "Type": "RESPONSIVE_AD", "Status": status, "State": state,
        "ResponsiveAd": {"AdImages": [{"AdImageHash": "hash-123"}]}}]}}


def test_direct_get_is_exact_id_scoped_and_read_only():
    query = prepare_ads_get(109)
    assert query["method"] == "get"
    assert query["params"]["SelectionCriteria"] == {"Ids": [109]}
    assert "ResponsiveAdFieldNames" in query["params"]
    for wrong in (True, 0, -1, "109", 2**63):
        with pytest.raises(ValueError):
            prepare_ads_get(wrong)


def test_provider_get_proves_exact_approved_creative_not_just_add_receipt():
    assert parse_ads_add_receipt({"result": {"AddResults": [{"Id": 109}]}}) == 109
    assert verify_ads_get(evidence(), expected=identity()) == {
        "verified": True, "status": "provider_verified", "object_id": "109"}
    for pending in (("MODERATION", "ON"), ("ACCEPTED", "OFF"), ("DRAFT", "OFF")):
        proof = verify_ads_get(evidence(status=pending[0], state=pending[1]), expected=identity())
        assert proof["verified"] is False
        assert proof["status"] == "pending"
    assert verify_ads_get(evidence(status="REJECTED"), expected=identity())["status"] == "rejected"


@pytest.mark.parametrize("malformed", [
    {}, {"error": {"error_code": 53}},
    {"result": {"AddResults": []}},
    {"result": {"AddResults": [{"Id": 1}, {"Id": 2}]}},
    {"result": {"AddResults": [{"Id": True}]}},
    {"result": {"AddResults": [{"Id": 109, "Warnings": [{"Code": 1}]}]}},
    {"result": {"AddResults": [{"Id": 109, "Errors": [{"Code": 1}]}]}},
])
def test_add_ambiguity_cannot_be_reported_published(malformed):
    with pytest.raises((RuntimeError, ValueError)):
        parse_ads_add_receipt(malformed)


def test_get_provider_identity_and_media_are_immutable():
    target = identity()
    for bad in (
        replace(target, ad_id=999),
        replace(target, campaign_id=999),
        replace(target, ad_group_id=999),
        replace(target, media_hash="different"),
    ):
        with pytest.raises((PermissionError, RuntimeError)):
            verify_ads_get(evidence(), expected=bad)
    for bad in (
        {}, {"error": {"code": 1}}, {"result": {"Ads": []}},
        {"result": {"Ads": evidence()["result"]["Ads"] * 2}},
    ):
        with pytest.raises(RuntimeError):
            verify_ads_get(bad, expected=target)


def test_wrong_creative_shape_does_not_verify_even_if_state_is_on():
    payload = evidence()
    payload["result"]["Ads"][0]["Type"] = "TEXT_AD"
    with pytest.raises(RuntimeError, match="ad_type"):
        verify_ads_get(payload, expected=identity())
    payload = evidence()
    payload["result"]["Ads"][0]["ResponsiveAd"]["AdImages"] = [{"AdImageHash": "other"}]
    with pytest.raises(PermissionError, match="media"):
        verify_ads_get(payload, expected=identity())


def test_owner_approval_and_execution_are_mandatory():
    args = dict(tenant_id="tenant", business_id="business", account_id="account",
                approval_reference="approved", execution_reference="reserved",
                ad_group_id=11, campaign_id=7, image_hash="hash-123")
    assert validate_publication_context(**args).media_hash == "hash-123"
    for key in ("tenant_id", "business_id", "account_id", "approval_reference", "execution_reference"):
        with pytest.raises(ValueError):
            validate_publication_context(**{**args, key: ""})
    for key in ("ad_group_id", "campaign_id"):
        with pytest.raises(ValueError):
            validate_publication_context(**{**args, key: True})


def test_combinatorial_add_request_is_scoped_to_one_existing_group():
    from interfaces.ads.yandex_direct_publication_proof import prepare_ads_add
    body = prepare_ads_add(ad_group_id=11, title="Консультация", description="Запись на встречу",
                           destination_url="https://shop.example.org/book", image_hash="hash-123")
    assert body == {"method": "add", "params": {"Ads": [{
        "AdGroupId": 11, "ResponsiveAd": {
            "Titles": ["Консультация"], "Texts": ["Запись на встречу"],
            "Href": "https://shop.example.org/book", "AdImageHashes": ["hash-123"],
        }}]}}
    assert "TextAd" not in str(body)


@pytest.mark.parametrize(("field", "value"), [
    ("ad_group_id", True), ("ad_group_id", 0),
    ("title", ""), ("title", "a" * 57),
    ("description", ""), ("description", "a" * 82),
    ("image_hash", "x"), ("image_hash", "hash with spaces"),
    ("destination_url", "http://shop.example.org"),
    ("destination_url", "https://shop.example.org@evil.org/path"),
    ("destination_url", "https://shop.example.org\\\\evil.org"),
])
def test_add_builder_rejects_bad_unapproved_inputs(field, value):
    from interfaces.ads.yandex_direct_publication_proof import prepare_ads_add
    args = dict(ad_group_id=11, title="Заголовок", description="Описание",
                destination_url="https://shop.example.org/book", image_hash="hash-123")
    with pytest.raises(ValueError):
        prepare_ads_add(**{**args, field: value})
