from __future__ import annotations

from runtime.boot.product_system_builder_pipeline import build_product_system_wiring_adapter
from runtime.modules.builtin_modules import (
    DEFAULT_RUNTIME_MODULE_IDS,
    build_builtin_runtime_modules,
)
from runtime.modules.decision_service_contract import build_decision_service_descriptor
from runtime.modules.registry import build_runtime_module_registry


class _Contract:
    def __init__(self) -> None:
        self.product_id = "prod"
        self.domain = "ads"

        class _OfferCatalog:
            catalog_id = "cat"

        class _TelemetrySchema:
            schema_id = "tel"

        self.offer_catalog = _OfferCatalog()
        self.telemetry_schema = _TelemetrySchema()
        self.modules = type("Modules", (), {"modules": []})()


class _SelectedReq:
    tenant_id = "t1"
    user_id = "u1"
    entrypoint = "telegram"


class _Selected:
    req = _SelectedReq()
    contract = _Contract()


class _Access:
    allowed = True
    reason = None
    missing_entitlements = ()


class _Enforced:
    selected = _Selected()
    access = _Access()



def test_build_runtime_module_registry_lists_shared_builtin_ids() -> None:
    registry = build_runtime_module_registry(build_builtin_runtime_modules())
    assert registry.list_ids() == tuple(sorted(DEFAULT_RUNTIME_MODULE_IDS))



def test_build_decision_service_descriptor_defaults() -> None:
    descriptor = build_decision_service_descriptor(domain="finance")
    assert descriptor.service_name == "decision_gateway"
    assert descriptor.domain == "finance"
    assert descriptor.source == "DecisionCore"



def test_wiring_adapter_uses_default_builtin_modules_when_contract_enables_none() -> None:
    registry = build_runtime_module_registry(build_builtin_runtime_modules())
    adapter = build_product_system_wiring_adapter(modules=registry)
    wired = adapter.wire_modules(_Enforced())
    services = wired.services
    assert "ring" in services
    assert "decision_gateway" in services
    assert "retention" in services
    assert "payments" in services
    assert "telemetry" in services
