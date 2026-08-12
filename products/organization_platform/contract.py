from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from contracts.product_contract import (
    EntryPolicy,
    EntitlementsSpec,
    ModuleSpec,
    ModulesSpec,
    ProductContract,
    TelemetryEventSpec,
    TelemetryField,
    TelemetrySchema,
)

from products.offer_catalog_resolver import resolve_offer_catalog
from runtime.platform.config.yaml_loader import load_yaml


class OrganizationPlatformPricingV1:
    pricing_model_id = "organization_platform_pricing_v1"

    def choose_offer_id(self, *, user_id: str, tenant_id: str, context: Mapping[str, Any]) -> str:
        stage = str((context or {}).get("lifecycle_stage") or "launch").strip().lower()
        if stage in {"scale", "growth"}:
            return "org_scale"
        return "org_launch"


def build_organization_platform_contract() -> ProductContract:
    entry_policy = EntryPolicy(
        entrypoints=("telegram", "webapp", "api"),
        default_entrypoint="telegram",
        requires_auth=True,
        requires_entitlement=False,
        required_entitlements=(),
    )

    products_dir = Path(__file__).resolve().parents[1]
    raw_product = load_yaml(products_dir / "organization_platform.yaml")
    offer_catalog = resolve_offer_catalog(raw_product, base_dir=products_dir)

    telemetry_events = (
        ("ui_click", (("button_id", "str", True), ("surface", "str", False))),
        ("offer_shown", (("offer_id", "str", True), ("placement", "str", False))),
        ("offer_clicked", (("offer_id", "str", True),)),
        ("purchase_attempt", (("offer_id", "str", True), ("provider", "str", False))),
        ("purchase_success", (("offer_id", "str", True), ("receipt_id", "str", False))),
        ("purchase_failed", (("offer_id", "str", True), ("reason", "str", False))),
        ("workspace_connected", (("workspace_id", "str", True), ("channel", "str", False))),
        ("campaign_synced", (("channel", "str", True), ("campaign_id", "str", False))),
        ("autopilot_action_applied", (("action_type", "str", True), ("actor", "str", False))),
    )
    telemetry_schema = TelemetrySchema(
        schema_id="organization_platform_telemetry_v1",
        events=tuple(
            TelemetryEventSpec(event_type, fields=tuple(TelemetryField(*field) for field in fields))
            for event_type, fields in telemetry_events
        ),
    )

    entitlements = EntitlementsSpec(keys=("workspace.access", "workspace.paid", "workspace.admin"))

    modules = ModulesSpec(
        modules=tuple(
            ModuleSpec(module_id=module_id, enabled_by_default=True)
            for module_id in ("ring", "decision_core", "retention", "payments", "telemetry")
        )
    )

    return ProductContract(
        tenant_id="*",
        product_id="organization_platform",
        domain="organization_platform",
        name="BusinesAIOS Workspace",
        entry_policy=entry_policy,
        offer_catalog=offer_catalog,
        pricing_model=OrganizationPlatformPricingV1(),
        telemetry_schema=telemetry_schema,
        entitlements=entitlements,
        modules=modules,
    )
