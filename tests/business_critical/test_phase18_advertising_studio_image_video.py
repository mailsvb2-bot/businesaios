"""Production-side boundaries for imported donor creative workflow."""
from __future__ import annotations

import pytest

from application.visual_creative_semantics.phase18_advertising_studio import (
    build_approved_generation_action, prepare_advertising_creatives, require_approved_visual_result,
)


@pytest.mark.parametrize("kind", ["image", "video"])
def test_three_deterministic_ad_drafts_without_implicit_publication(kind):
    args = dict(tenant_id="t1", business_id="b1", campaign_id="c1",
                headline="Professional consultation", description="Booking a consultation",
                brand_context="Blue and white identity", campaign_goal="Consultation booking",
                kind=kind, formats=("square", "story"))
    first = prepare_advertising_creatives(**args)
    assert first == prepare_advertising_creatives(**args)
    assert len(first) == 3
    assert len({item.creative_id for item in first}) == 3
    assert all(row.generation_status == "draft" and row.publication_status == "not_authorized"
               and row.spend_authorized is False for row in first)
    assert all("fake reviews" in row.prompt for row in first)
    for variation in ("other tenant", "different brand"):
        modified = dict(args)
        if variation == "other tenant":
            modified["tenant_id"] = "t2"
        else:
            modified["brand_context"] = "Independent new brand"
        changed = prepare_advertising_creatives(**modified)
        assert not set(row.creative_id for row in first) & set(row.creative_id for row in changed)


@pytest.mark.parametrize("change", [
    {"kind": "audio"},
    {"formats": ("portrait",)},
    {"formats": ("story", "story")},
    {"formats": ()},
    {"headline": ""},
    {"brand_context": ""},
    {"country_code": "RU1"},
])
def test_invalid_generation_inputs_never_produce_drafts(change):
    args = dict(tenant_id="t1", business_id="b1", campaign_id="c1",
                headline="Consultation", description="Professional help",
                brand_context="A real brand", campaign_goal="Bookings",
                kind="image", formats=("square",))
    args.update(change)
    with pytest.raises(ValueError):
        prepare_advertising_creatives(**args)


def test_generation_receipt_cannot_publish_spend_or_cross_scope():
    brief = prepare_advertising_creatives(
        tenant_id="t1", business_id="b1", campaign_id="c1",
        headline="Consultation", description="Professional help",
        brand_context="A real brand", campaign_goal="Bookings",
        kind="video", formats=("story",),
    )[0]
    receipt = dict(tenant_id="t1", business_id="b1",
                   creative_id=brief.creative_id, approval_fingerprint=brief.approval_fingerprint,
                   kind="video", status="succeeded", sha256="a" * 64)
    result = require_approved_visual_result(
        brief=brief, approved_fingerprint=brief.approval_fingerprint, receipt=receipt,
    )
    assert result["verified_generation"] is True
    assert result["published"] is False
    assert result["spend_authorized"] is False
    with pytest.raises(PermissionError):
        require_approved_visual_result(brief=brief, approved_fingerprint="stale", receipt=receipt)
    for key, value in [("tenant_id", "t2"), ("business_id", "b2"),
                       ("status", "running"), ("sha256", "x" * 64), ("kind", "image")]:
        bad = dict(receipt, **{key: value})
        with pytest.raises(RuntimeError):
            require_approved_visual_result(
                brief=brief, approved_fingerprint=brief.approval_fingerprint, receipt=bad,
            )


def test_reviewed_ad_uses_existing_visual_action_without_direct_provider_effects():
    brief = prepare_advertising_creatives(
        tenant_id="t1", business_id="b1", campaign_id="campaign-1",
        headline="Consultation", description="Professional service",
        brand_context="Real brand identity", campaign_goal="Bookings",
        kind="video", formats=("story",),
    )[0]
    seen = []

    def approval(**kwargs):
        seen.append(kwargs)
        return kwargs["fingerprint"] == brief.approval_fingerprint

    action = build_approved_generation_action(
        brief=brief, approval_reference="signed-review-1",
        verify_approval=approval, user_id="owner-1",
    )
    assert action["action_type"] == "visual_creative_generate@v1"
    assert action["requires_canonical_execution"] is True
    assert action["spend_authorized"] is False
    assert action["payload"]["kind"] == "video"
    assert action["payload"]["brand_context"] == "Real brand identity"
    assert action["payload"]["brand_context"] != brief.brand_fingerprint
    assert action["payload"]["aspect_ratio"] == "9:16"
    assert seen[0]["tenant_id"] == "t1"
    assert seen[0]["campaign_id"] == "campaign-1"
    with pytest.raises(PermissionError, match="approval_denied"):
        build_approved_generation_action(
            brief=brief, approval_reference="signed-review-1",
            verify_approval=lambda **kwargs: False, user_id="owner-1",
        )
