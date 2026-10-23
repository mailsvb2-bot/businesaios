"""Production-side boundaries for imported donor creative workflow."""
from __future__ import annotations

import pytest

from application.visual_creative_semantics.phase18_advertising_studio import (
    build_approved_generation_action,
    prepare_advertising_creatives,
    require_approved_visual_result,
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
    assert all(row.prompt.startswith("Рекламный") and "Avoid" not in row.prompt for row in first)
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
    assert action["payload"]["variants"] == 1
    assert action["payload"]["overlay"] == {}
    assert action["approval_binding"]["creative_id"] == brief.creative_id
    assert not {"approval_reference", "approval_fingerprint", "creative_id", "campaign_id"} & set(action["payload"])
    assert seen[0]["tenant_id"] == "t1"
    assert seen[0]["campaign_id"] == "campaign-1"
    with pytest.raises(PermissionError, match="approval_denied"):
        build_approved_generation_action(
            brief=brief, approval_reference="signed-review-1",
            verify_approval=lambda **kwargs: False, user_id="owner-1",
        )


def test_reviewed_image_action_generates_owner_selectable_candidates_and_overlay():
    from core.actions.catalog_groups import ads_catalog
    brief = prepare_advertising_creatives(
        tenant_id="tenant-1", business_id="business-1", campaign_id="campaign-1",
        headline="Сервис", description="Запись на приём",
        brand_context="Сдержанный синий стиль", campaign_goal="Записи",
        kind="image", formats=("square", "story"),
    )[0]
    action = build_approved_generation_action(
        brief=brief, approval_reference="approval-1",
        verify_approval=lambda **kwargs: True, user_id="owner-1",
    )
    payload = action["payload"]
    assert payload["variants"] == 3
    assert payload["overlay"]["headline"] == "Сервис"
    assert payload["overlay"]["formats"] == ["square", "story"]
    assert action["spend_authorized"] is False
    schema = ads_catalog()["visual_creative_generate@v1"]
    assert schema is not None
    assert action["approval_binding"]["approval_fingerprint"] == brief.approval_fingerprint


def _cs_briefs(**kw):
    base = dict(tenant_id="t1", business_id="b1", campaign_id="c1", headline="Консультация",
                description="Запишитесь на встречу", brand_context="Синий", campaign_goal="Записи",
                kind="image", formats=("square", "story"))
    return prepare_advertising_creatives(**{**base, **kw})


def test_cs_preflight_and_render_key():
    from application.visual_creative_semantics.phase18_advertising_studio import (
        overlay_for,
        preflight,
        render_idempotency_key,
    )
    assert preflight("Ок", "Ок") == (100, ())
    score, issues = preflight("Гарантированно лучший в мире", "x" * 301)
    assert "risky_claim" in issues and "body_long_for_layout" in issues and score == 55
    a, b, c = _cs_briefs()
    assert [overlay_for(x)["layout"] for x in (a, b, c)] == ["lower_card", "top_card", "lower_card"]
    assert render_idempotency_key(a) == render_idempotency_key(_cs_briefs()[0])
    assert render_idempotency_key(a) != render_idempotency_key(_cs_briefs(formats=("square",))[0])
    assert render_idempotency_key(a).startswith(a.creative_id + ":render:")


def test_cs_risky_claim_blocks_generation_action():
    brief = _cs_briefs(headline="100% гарантия результата")[0]
    with pytest.raises(ValueError, match="unsafe_advertising_creative_variant"):
        build_approved_generation_action(brief=brief, approval_reference="r",
                                         verify_approval=lambda **k: True, user_id="owner-1")
