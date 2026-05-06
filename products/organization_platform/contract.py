from __future__ import annotations

from typing import Any, Mapping

from contracts.product_contract import (
    EntryPolicy,
    EntitlementsSpec,
    ModuleSpec,
    ModulesSpec,
    Offer,
    OfferCatalog,
    ProductContract,
    TelemetryEventSpec,
    TelemetryField,
    TelemetrySchema,
)


class OrganizationPlatformPricingV1:
    pricing_model_id = "organization_platform_pricing_v1"

    def choose_offer_id(self, *, user_id: str, tenant_id: str, context: Mapping[str, Any]) -> str:
        stage = str((context or {}).get("lifecycle_stage") or "launch").strip().lower()
        if stage in {"scale", "growth"}:
            return "org_scale_suite_2990"
        return "org_launch_990"


def build_organization_platform_contract() -> ProductContract:
    entry_policy = EntryPolicy(
        entrypoints=("telegram", "webapp", "api"),
        default_entrypoint="telegram",
        requires_auth=True,
        requires_entitlement=False,
        required_entitlements=(),
    )

    offer_catalog = OfferCatalog(
        catalog_id="organization_platform_offers_v1",
        offers=(
            Offer(
                offer_id="org_launch_990",
                title="Launch Workspace",
                price_minor=99000,
                currency="RUB",
                period_days=30,
                tags=("subscription", "launch"),
            ),
            Offer(
                offer_id="org_scale_suite_2990",
                title="Scale Suite",
                price_minor=299000,
                currency="RUB",
                period_days=30,
                tags=("subscription", "scale"),
            ),
        ),
    )

    telemetry_schema = TelemetrySchema(
        schema_id="organization_platform_telemetry_v1",
        events=(
            TelemetryEventSpec(
                event_type="ui_click",
                fields=(TelemetryField("button_id", "str"), TelemetryField("surface", "str", required=False)),
            ),
            TelemetryEventSpec(
                event_type="offer_shown",
                fields=(TelemetryField("offer_id", "str"), TelemetryField("placement", "str", required=False)),
            ),
            TelemetryEventSpec(event_type="offer_clicked", fields=(TelemetryField("offer_id", "str"),)),
            TelemetryEventSpec(
                event_type="purchase_attempt",
                fields=(TelemetryField("offer_id", "str"), TelemetryField("provider", "str", required=False)),
            ),
            TelemetryEventSpec(
                event_type="purchase_success",
                fields=(TelemetryField("offer_id", "str"), TelemetryField("receipt_id", "str", required=False)),
            ),
            TelemetryEventSpec(
                event_type="purchase_failed",
                fields=(TelemetryField("offer_id", "str"), TelemetryField("reason", "str", required=False)),
            ),
            TelemetryEventSpec(
                event_type="workspace_connected",
                fields=(TelemetryField("workspace_id", "str"), TelemetryField("channel", "str", required=False)),
            ),
            TelemetryEventSpec(
                event_type="campaign_synced",
                fields=(TelemetryField("channel", "str"), TelemetryField("campaign_id", "str", required=False)),
            ),
            TelemetryEventSpec(
                event_type="autopilot_action_applied",
                fields=(TelemetryField("action_type", "str"), TelemetryField("actor", "str", required=False)),
            ),
        ),
    )

    entitlements = EntitlementsSpec(keys=("workspace.access", "workspace.paid", "workspace.admin"))

    modules = ModulesSpec(
        modules=(
            ModuleSpec(module_id="ring", enabled_by_default=True),
            ModuleSpec(module_id="decision_core", enabled_by_default=True),
            ModuleSpec(module_id="retention", enabled_by_default=True),
            ModuleSpec(module_id="payments", enabled_by_default=True),
            ModuleSpec(module_id="telemetry", enabled_by_default=True),
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
