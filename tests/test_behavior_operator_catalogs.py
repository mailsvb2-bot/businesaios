from __future__ import annotations

from pathlib import Path

from core.behavior.complex4 import Complex4
from core.behavior.dirac_operators import apply_event_operator
from core.behavior.operator_catalogs import (
    OperatorCatalogKey,
    OperatorCatalogResolver,
    default_operator_catalog_registry,
    resolve_operator_context,
)


def test_default_operator_catalog_registry_loads() -> None:
    reg = default_operator_catalog_registry()
    assert reg.get("default") is not None


def test_operator_catalog_resolver_chain() -> None:
    r = OperatorCatalogResolver()
    cat = r.resolve(
        key=OperatorCatalogKey(tenant_id="default", product_id="organization_platform", environment="prod"),
        fallback_catalog_id="default",
    )
    assert cat.catalog_id in {"default:organization_platform:prod", "default"}


def test_apply_event_operator_uses_catalog_params_bounded() -> None:
    # ensure operator works and stays normalized
    psi0 = Complex4.zeros().renormalize(target_norm=1.0)
    ctx = {
        "tenant_id": "default",
        "product_id": "organization_platform",
        "domain": "organization_platform",
        "environment": "prod",
        "operator_catalog_id": "default",
    }
    out = apply_event_operator(
        psi=psi0,
        anti=0.0,
        event={"event_type": "purchase_success", "payload": {}},
        context=ctx,
    )
    assert 0.0 <= out.anti <= 1.0
    assert abs(out.psi.norm2() - 1.0) < 1e-6


def test_resolve_operator_context_from_product_dict() -> None:
    product = {
        "product_id": "organization_platform",
        "domain": "organization_platform",
        "environment": "prod",
        "modules": {
            "behavior_os": {
                "enabled": True,
                "operator_catalog_ref": "default",
                "operator_overrides": {"phase_gain": 0.1},
            }
        },
    }
    ctx = resolve_operator_context(product=product, tenant_id="default")
    assert ctx["operator_catalog_id"] == "default"
    assert isinstance(ctx.get("operator_overrides"), dict)
    assert float(ctx["operator_overrides"].get("phase_gain")) == 0.1
