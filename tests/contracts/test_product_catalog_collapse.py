from __future__ import annotations

from pathlib import Path

from products.organization_platform.contract import build_organization_platform_contract
from products.pricing_models import ContextOfferPricingModel
from products.product_loader import ProductLoader

ROOT = Path(__file__).resolve().parents[2]


def test_organization_facade_is_exact_loader_projection() -> None:
    canonical = ProductLoader(base_dir=ROOT / "products").load("organization_platform.yaml")
    facade = build_organization_platform_contract()
    assert facade.as_dict() == canonical.as_dict()
    assert facade.entry_policy.entrypoints == ("telegram", "webapp", "api")
    assert facade.entitlements.keys == ("workspace.access", "workspace.paid", "workspace.admin")


def test_ladder_pricing_selects_existing_offer_ids_without_owning_prices() -> None:
    contract = ProductLoader(base_dir=ROOT / "products").load("organization_platform.yaml")
    assert isinstance(contract.pricing_model, ContextOfferPricingModel)
    known = {offer.offer_id for offer in contract.offer_catalog.offers}
    assert contract.pricing_model.choose_offer_id(user_id="u", tenant_id="t", context={}) == "org_launch"
    assert contract.pricing_model.choose_offer_id(user_id="u", tenant_id="t", context={"lifecycle_stage": "growth"}) == "org_scale"
    assert contract.pricing_model.choose_offer_id(user_id="u", tenant_id="t", context={"lifecycle_stage": "scale"}) == "org_scale"
    assert {"org_launch", "org_scale"}.issubset(known)


def test_capability_modules_do_not_drive_runtime_module_wiring() -> None:
    from runtime.boot.product_system_builder_pipeline import build_product_system_wiring_adapter
    from runtime.modules.builtin_modules import build_builtin_runtime_modules
    from runtime.modules.registry import build_runtime_module_registry

    contract = ProductLoader(base_dir=ROOT / "products").load("organization_platform.yaml")
    req = type("Req", (), {"tenant_id": "tenant", "user_id": "user", "entrypoint": "telegram"})()
    selected = type("Selected", (), {"req": req, "contract": contract})()
    access = type("Access", (), {"allowed": True, "reason": "", "missing_entitlements": ()})()
    enforced = type("Enforced", (), {"selected": selected, "access": access})()
    registry = build_runtime_module_registry(build_builtin_runtime_modules())
    wired = build_product_system_wiring_adapter(modules=registry).wire_modules(enforced)
    assert set(wired.services) >= {"ring", "decision_gateway", "retention", "payments", "telemetry"}
    assert "offers" not in wired.services
    assert "pricing" not in wired.services
