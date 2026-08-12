from products.organization_platform.contract import build_organization_platform_contract


def test_builtin_organization_platform_contract_uses_canonical_external_catalog() -> None:
    contract = build_organization_platform_contract()
    offers = {offer.offer_id: offer.price_minor for offer in contract.offer_catalog.offers}

    assert contract.offer_catalog.catalog_id == "offer_catalog_organization_platform@v1"
    assert offers == {"org_launch": 99_000, "org_scale": 299_000}
    assert contract.pricing_model.choose_offer_id(user_id="u", tenant_id="t", context={}) == "org_launch"
    assert contract.pricing_model.choose_offer_id(
        user_id="u", tenant_id="t", context={"lifecycle_stage": "growth"}
    ) == "org_scale"
