from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True
CANON_PRODUCT_SYSTEM_WIRING_ADAPTER_OWNER = True

"""Phase adapters for the product-contract boot pipeline."""

from runtime.boot.boot_context import (
    AccessEnforced,
    AccessEnforcerPort,
    ModulesWired,
    ModuleWiringPort,
    ProductSelectorPort,
    SelectedProduct,
)
from bootstrap.product_system_builder_contracts import RuntimeView
from runtime.boot.system_builder_products import RuntimeRequest, SystemBuilderProducts
from runtime.modules.builtin_modules import DEFAULT_RUNTIME_MODULE_IDS
from runtime.modules.module_protocol import ModuleWiringContext
from runtime.modules.registry import ModuleRegistry
from runtime.platform.identity.enforcement import ProductAccessEnforcer


class SelectorAdapter(ProductSelectorPort):
    def __init__(self, *, products: SystemBuilderProducts) -> None:
        self._products = products

    def select_product(self, req):
        booted = self._products.boot_product(
            RuntimeRequest(
                tenant_id=req.tenant_id,
                user_id=req.user_id,
                entrypoint=req.entrypoint,
                hints=req.hints,
            )
        )
        return SelectedProduct(req=req, contract=booted.contract)


class EnforcerAdapter(AccessEnforcerPort):
    def __init__(self, *, enforcer: ProductAccessEnforcer) -> None:
        self._enforcer = enforcer

    def enforce_access(self, selected: SelectedProduct) -> AccessEnforced:
        req = selected.req
        access = self._enforcer.enforce(
            tenant_id=req.tenant_id,
            user_id=req.user_id,
            contract=selected.contract,
        )
        return AccessEnforced(selected=selected, access=access)


class WiringAdapter(ModuleWiringPort):
    def __init__(self, *, modules: ModuleRegistry) -> None:
        self._modules = modules

    def wire_modules(self, enforced: AccessEnforced) -> ModulesWired:
        selected = enforced.selected
        contract = selected.contract
        if not enforced.access.allowed:
            return ModulesWired(
                enforced=enforced,
                services={
                    "access_denied": {
                        "reason": enforced.access.reason,
                        "missing": enforced.access.missing_entitlements,
                    }
                },
            )
        wiring = ModuleWiringContext(services={})
        view = RuntimeView(
            tenant_id=selected.req.tenant_id,
            user_id=selected.req.user_id,
            entrypoint=selected.req.entrypoint,
            contract=contract,
        )
        wired_any = False
        for module_spec in contract.modules.modules:
            if not module_spec.enabled_by_default:
                continue
            module = self._modules.get(module_spec.module_id)
            module.wire(product=view, module_config=dict(module_spec.config), ctx=wiring)
            wired_any = True
        if not wired_any:
            _wire_default_builtin_modules(modules=self._modules, view=view, wiring=wiring)
        return ModulesWired(enforced=enforced, services=wiring.services)



def build_product_system_wiring_adapter(*, modules: ModuleRegistry) -> WiringAdapter:
    return WiringAdapter(modules=modules)



def _wire_default_builtin_modules(*, modules: ModuleRegistry, view: RuntimeView, wiring: ModuleWiringContext) -> None:
    for module_id in DEFAULT_RUNTIME_MODULE_IDS:
        module = modules.get(module_id)
        module.wire(product=view, module_config={}, ctx=wiring)


__all__ = [
    "CANON_PRODUCT_SYSTEM_WIRING_ADAPTER_OWNER",
    "EnforcerAdapter",
    "SelectorAdapter",
    "WiringAdapter",
    "build_product_system_wiring_adapter",
]
