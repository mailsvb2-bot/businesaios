from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from contracts.product_contract import TelemetryEventSpec, TelemetryField, TelemetrySchema


def _default_schema() -> TelemetrySchema:
    return TelemetrySchema(
        schema_id="telemetry_default@v1",
        events=(
            TelemetryEventSpec("ui_click", fields=(TelemetryField("button", "str", True),)),
            TelemetryEventSpec("paywall_opened", fields=()),
            TelemetryEventSpec("paywall_closed", fields=()),
            TelemetryEventSpec("offer_shown", fields=(TelemetryField("offer_id", "str", True),)),
            TelemetryEventSpec("offer_clicked", fields=(TelemetryField("offer_id", "str", True),)),
            TelemetryEventSpec("purchase_attempt", fields=(TelemetryField("offer_id", "str", True),)),
            TelemetryEventSpec("purchase_success", fields=(TelemetryField("offer_id", "str", True),)),
            TelemetryEventSpec("purchase_failed", fields=(TelemetryField("offer_id", "str", True),)),
            TelemetryEventSpec("mood_logged", fields=(TelemetryField("mood", "json", True),)),
            TelemetryEventSpec("audio_sent", fields=(TelemetryField("audio_id", "str", True),)),
            TelemetryEventSpec("audio_started", fields=(TelemetryField("audio_id", "str", True), TelemetryField("length_s", "int", False))),
            TelemetryEventSpec(
                "audio_progress",
                fields=(
                    TelemetryField("audio_id", "str", True),
                    TelemetryField("delta_s", "int", True),
                ),
            ),
            TelemetryEventSpec("audio_stopped", fields=(TelemetryField("audio_id", "str", True), TelemetryField("pos_s", "int", False))),
            TelemetryEventSpec("audio_completed", fields=(TelemetryField("audio_id", "str", True),)),
        ),
    )


def _organization_platform_schema() -> TelemetrySchema:
    fields = {
        "ui_click": (("button_id", "str", True), ("surface", "str", False)),
        "offer_shown": (("offer_id", "str", True), ("placement", "str", False)),
        "offer_clicked": (("offer_id", "str", True),),
        "purchase_attempt": (("offer_id", "str", True), ("provider", "str", False)),
        "purchase_success": (("offer_id", "str", True), ("receipt_id", "str", False)),
        "purchase_failed": (("offer_id", "str", True), ("reason", "str", False)),
        "workspace_connected": (("workspace_id", "str", True), ("channel", "str", False)),
        "campaign_synced": (("channel", "str", True), ("campaign_id", "str", False)),
        "autopilot_action_applied": (("action_type", "str", True), ("actor", "str", False)),
    }
    return TelemetrySchema(
        schema_id="organization_platform_telemetry_v1",
        events=tuple(
            TelemetryEventSpec(event_type, tuple(TelemetryField(*field) for field in event_fields))
            for event_type, event_fields in fields.items()
        ),
    )


def resolve_telemetry_schema(raw: Mapping[str, Any]) -> TelemetrySchema:
    ts = raw.get("telemetry_schema") if isinstance(raw.get("telemetry_schema"), dict) else {}
    sid = str(ts.get("id") or "telemetry_default@v1")

    # Only known schemas are allowed; unknown => safe default.
    if sid == "telemetry_default@v1":
        schema = _default_schema()
        schema.validate()
        return schema
    if sid == "organization_platform_telemetry_v1":
        schema = _organization_platform_schema()
        schema.validate()
        return schema

    schema = _default_schema()
    schema.validate()
    return schema
