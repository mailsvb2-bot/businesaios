from __future__ import annotations

from canon import (
    LayerAssessment,
    SimplificationClass,
    SimplificationIntent,
    SimplificationProposal,
    SimplificationVerdict,
    assert_canon_simplification,
    classify_layer_for_simplification,
)
from core.retention.config.ai_limits import LIMITS, is_allowed_arm, is_allowed_discount_pct
from core.retention.config.pricing_ladder import (
    ALLOWED_DISCOUNTS_PCT,
    OfferWindow,
    base_price_for_arm,
    retention_boot_prices,
    window_for_arm,
)


def test_retention_ai_limits_is_thin_compat_layer_over_pricing_ladder() -> None:
    verdict = classify_layer_for_simplification(
        LayerAssessment(
            name="core.retention.config.ai_limits",
            layer_class=SimplificationClass.COMPAT_SHIM,
            has_real_domain_logic=False,
            enforces_safety_invariant=True,
            enforces_decision_discipline=False,
            preserves_observability=False,
            is_public_contract=True,
        )
    )
    assert verdict == SimplificationVerdict.KEEP
    assert tuple(int(v) for v in LIMITS.allowed_discounts_pct) == tuple(int(v) for v in ALLOWED_DISCOUNTS_PCT)


def test_retention_pricing_ladder_is_meaningful_layer_and_cannot_be_deleted() -> None:
    proposal = SimplificationProposal(
        target="core.retention.config.pricing_ladder",
        intent=SimplificationIntent.DELETE,
        assessments=(
            LayerAssessment(
                name="core.retention.config.pricing_ladder",
                layer_class=SimplificationClass.DOMAIN_LOGIC,
                has_real_domain_logic=True,
                enforces_safety_invariant=True,
                enforces_decision_discipline=False,
                preserves_observability=False,
                is_public_contract=False,
            ),
        ),
        expected_verdict=SimplificationVerdict.DELETE_AS_DUPLICATE,
        preserves_functionality=True,
        preserves_decision_discipline=True,
        preserves_safety=True,
        preserves_observability=True,
        preserves_domain_boundaries=True,
        regression_tests_added=True,
    )

    try:
        assert_canon_simplification(proposal)
    except ValueError as exc:
        assert "cannot_simplify_meaningful_layer:core.retention.config.pricing_ladder" in str(exc)
    else:
        raise AssertionError("meaningful retention pricing ladder must not be deletable")


def test_retention_pricing_helpers_preserve_existing_values() -> None:
    assert base_price_for_arm("offer_30_14900") == 14900
    assert base_price_for_arm("offer_90_21900") == 21900
    assert base_price_for_arm("offer_bundle_14_30") == 24900
    assert window_for_arm("offer_30_14900") == OfferWindow(day_from=1, day_to=365)
    assert window_for_arm("offer_90_21900") == OfferWindow(day_from=35, day_to=55)
    assert retention_boot_prices() == {"p30": 14900, "p90": 21900, "bundle_14_30": 24900}


def test_retention_ai_limit_helpers_preserve_allowed_surface() -> None:
    assert is_allowed_arm("offer_30_14900") is True
    assert is_allowed_arm("missing") is False
    assert is_allowed_discount_pct(10) is True
    assert is_allowed_discount_pct("15") is True
    assert is_allowed_discount_pct(99) is False
