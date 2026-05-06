from __future__ import annotations

import importlib


def test_canonical_modules_exist() -> None:
    """Hard lock: key canonical modules must exist."""

    required = [
        "runtime.platform.event_store.event_types",
        "core.read_model.reducers",
        "core.read_model.world_state_builder",
        "contracts.product_contract",
        "core.retention.constraints",
        "core.llm.agent.agent",
        "core.ads.ads_service",
    ]
    for m in required:
        importlib.import_module(m)


def test_retention_event_types_is_reexport_only() -> None:
    """Hard lock: retention must not maintain divergent vocabulary."""

    m = importlib.import_module("core.retention.event_types")
    assert getattr(m, "UI_CLICK") == "ui_click"
    assert getattr(m, "OFFER_SHOWN") == "offer_shown"
    assert getattr(m, "PURCHASE_SUCCESS") == "purchase_success"


def test_core_products_product_contract_is_compat_reexport() -> None:
    """Hard lock: legacy import path must point to canonical contract."""

    legacy = importlib.import_module("core.products.product_contract")
    canon = importlib.import_module("contracts.product_contract")
    assert getattr(legacy, "ProductContract") is getattr(canon, "ProductContract")
