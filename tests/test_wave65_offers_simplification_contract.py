from __future__ import annotations

from dataclasses import dataclass, field

from canon import (
    LayerAssessment,
    SimplificationClass,
    SimplificationIntent,
    SimplificationProposal,
    SimplificationVerdict,
    assert_canon_simplification,
    classify_layer_for_simplification,
)
from core.offers.catalog_registry import OfferCatalogRegistry
from core.offers.engine import OfferEngine
from core.offers.offer_catalog_resolver import OfferCatalogResolver
from core.offers.offer_types import OfferCatalog, OfferEligibility, OfferRender


@dataclass(frozen=True)
class _Catalog(OfferCatalog):
    id: str
    _offers: dict = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_offers", {
            "offer_x": {"cooldown_days": 7},
            self.id: {},
        })

    def list_offers(self):
        return []

    def eligibility(self, *, offer_id: str, context):
        return OfferEligibility(ok=True)

    def render(self, *, offer_id: str, user_id: str, price_rub: int, variant: str, context):
        return OfferRender(offer_id=offer_id, variant=variant, price_rub=price_rub, text=offer_id, meta={})


def test_offers_catalog_resolution_shim_is_only_thin_adapter() -> None:
    verdict = classify_layer_for_simplification(
        LayerAssessment(
            name="core.offers.catalog_resolution",
            layer_class=SimplificationClass.COMPAT_SHIM,
            has_real_domain_logic=False,
            enforces_safety_invariant=False,
            enforces_decision_discipline=False,
            preserves_observability=False,
            is_public_contract=True,
            only_proxies_data=True,
        )
    )
    assert verdict == SimplificationVerdict.KEEP_AS_THIN_ADAPTER


def test_offers_resolver_is_meaningful_layer_and_cannot_be_deleted() -> None:
    proposal = SimplificationProposal(
        target="core.offers.offer_catalog_resolver",
        intent=SimplificationIntent.DELETE,
        assessments=(
            LayerAssessment(
                name="core.offers.offer_catalog_resolver",
                layer_class=SimplificationClass.DOMAIN_LOGIC,
                has_real_domain_logic=True,
                enforces_safety_invariant=False,
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
        assert "cannot_simplify_meaningful_layer:core.offers.offer_catalog_resolver" in str(exc)
    else:
        raise AssertionError("meaningful offers resolver must not be deletable")


def test_offer_engine_cooldown_path_uses_same_canonical_resolver_logic() -> None:
    registry = OfferCatalogRegistry(_by_id={})
    registry.register(_Catalog(id="offer_catalog_legacy@v1"))
    registry.register(_Catalog(id="tenantA:product1:prod"))

    engine = OfferEngine(catalogs=registry)
    product = {"product_id": "product1", "offer_catalog": {"id": "offer_catalog_legacy@v1"}}

    ok, meta = engine.should_show_offer(
        now_ms=10_000_000,
        product=product,
        tenant_id="tenantA",
        user_id="u1",
        entitlements={},
        payment_status=None,
        offer_id="offer_x",
        cooldown_store=None,
    )

    assert ok is True
    assert meta["cooldown_days"] == 7

    cat = OfferCatalogResolver(catalogs=registry).resolve_for_product(
        product=product,
        tenant_id="tenantA",
        context=None,
    )
    assert getattr(cat, "id", None) == "tenantA:product1:prod"
