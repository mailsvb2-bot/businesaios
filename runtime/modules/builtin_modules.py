from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from runtime.modules.decision_service_contract import build_decision_service_descriptor
from runtime.modules.module_protocol import ModuleWiringContext, ProductRuntimeView

CANON_RUNTIME_MODULE_CATALOG_OWNER = True
DEFAULT_RUNTIME_MODULE_IDS: tuple[str, ...] = (
    "ring",
    "decision_core",
    "retention",
    "payments",
    "telemetry",
)


class RingModule:
    module_id = "ring"

    def wire(
        self,
        *,
        product: ProductRuntimeView,
        module_config: Mapping[str, Any],
        ctx: ModuleWiringContext,
    ) -> None:
        ctx.services.setdefault("ring", {"enabled": True, "product_id": product.contract.product_id})


class DecisionCoreModule:
    module_id = "decision_core"

    def wire(
        self,
        *,
        product: ProductRuntimeView,
        module_config: Mapping[str, Any],
        ctx: ModuleWiringContext,
    ) -> None:
        descriptor = build_decision_service_descriptor(domain=product.contract.domain)
        ctx.services.setdefault("decision_gateway", descriptor.__dict__.copy())


class RetentionModule:
    module_id = "retention"

    def wire(
        self,
        *,
        product: ProductRuntimeView,
        module_config: Mapping[str, Any],
        ctx: ModuleWiringContext,
    ) -> None:
        ctx.services.setdefault("retention", {"enabled": True})


class PaymentsModule:
    module_id = "payments"

    def wire(
        self,
        *,
        product: ProductRuntimeView,
        module_config: Mapping[str, Any],
        ctx: ModuleWiringContext,
    ) -> None:
        ctx.services.setdefault(
            "payments",
            {"enabled": True, "catalog_id": product.contract.offer_catalog.catalog_id},
        )


class TelemetryModule:
    module_id = "telemetry"

    def wire(
        self,
        *,
        product: ProductRuntimeView,
        module_config: Mapping[str, Any],
        ctx: ModuleWiringContext,
    ) -> None:
        ctx.services.setdefault(
            "telemetry",
            {"enabled": True, "schema_id": product.contract.telemetry_schema.schema_id},
        )


def build_builtin_runtime_modules() -> tuple[object, ...]:
    return (
        RingModule(),
        DecisionCoreModule(),
        RetentionModule(),
        PaymentsModule(),
        TelemetryModule(),
    )


def load_builtin_modules() -> tuple[object, ...]:
    return build_builtin_runtime_modules()


__all__ = [
    "CANON_RUNTIME_MODULE_CATALOG_OWNER",
    "DEFAULT_RUNTIME_MODULE_IDS",
    "DecisionCoreModule",
    "PaymentsModule",
    "RetentionModule",
    "RingModule",
    "TelemetryModule",
    "build_builtin_runtime_modules",
    "load_builtin_modules",
]
