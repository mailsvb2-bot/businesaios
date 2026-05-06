from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True
TRANSITIONAL_PRODUCT_SYSTEM_BUILDER = True

"""Product-contract boot path.

This builder is intentionally transitional until the legacy and product-contract
boot paths converge on a single canonical composition root. The file stays thin
so it does not become a second boot architecture.
"""

from runtime.boot.boot_context import BootPipeline, BootRequest, ReadySystem
from bootstrap.product_system_builder_contracts import ProductContractSystem
from bootstrap.product_system_builder_pipeline import (
    EnforcerAdapter,
    SelectorAdapter,
    build_product_system_wiring_adapter,
)
from runtime.boot.system_builder_products import SystemBuilderProducts
from runtime.modules.builtin_modules import build_builtin_runtime_modules
from runtime.modules.registry import ModuleRegistry, build_runtime_module_registry
from runtime.platform.identity.entitlements import (
    AccessController,
    EntitlementsProvider,
    IdentityProvider,
    InMemoryEntitlementsProvider,
    InMemoryIdentityProvider,
)
from runtime.platform.identity.enforcement import ProductAccessEnforcer


class SystemBuilder:
    def __init__(
        self,
        *,
        default_product_id: str = "organization_platform",
        identity_provider: IdentityProvider | None = None,
        entitlements_provider: EntitlementsProvider | None = None,
        module_registry: ModuleRegistry | None = None,
    ) -> None:
        self._products = SystemBuilderProducts(default_product_id=default_product_id)
        identity = identity_provider or InMemoryIdentityProvider(authenticated_users=set())
        entitlements = entitlements_provider or InMemoryEntitlementsProvider(grants={})
        self._access = ProductAccessEnforcer(
            controller=AccessController(identity=identity, entitlements=entitlements)
        )
        self._modules = module_registry or build_runtime_module_registry(build_builtin_runtime_modules())
        self._pipeline = BootPipeline(
            selector=SelectorAdapter(products=self._products),
            enforcer=EnforcerAdapter(enforcer=self._access),
            wiring=build_product_system_wiring_adapter(modules=self._modules),
        )

    def build(
        self,
        *,
        tenant_id: str,
        user_id: str,
        entrypoint: str,
        hints: dict[str, str],
    ) -> ProductContractSystem:
        ready: ReadySystem = self._pipeline.boot(
            BootRequest(
                tenant_id=tenant_id,
                user_id=user_id,
                entrypoint=entrypoint,
                hints=hints,
            )
        )
        return ProductContractSystem(
            services=ready.services,
            product_id=ready.product_id,
            domain=ready.domain,
            access=ready.access,
        )


__all__ = [
    "CANON_BOOT_WIRING_ONLY",
    "TRANSITIONAL_PRODUCT_SYSTEM_BUILDER",
    "ProductContractSystem",
    "SystemBuilder",
]
