from __future__ import annotations

from typing import Any, Mapping

from contracts.product_contract import TelemetryField, TelemetryEventSpec, TelemetrySchema


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


def resolve_telemetry_schema(raw: Mapping[str, Any]) -> TelemetrySchema:
    ts = raw.get("telemetry_schema") if isinstance(raw.get("telemetry_schema"), dict) else {}
    sid = str(ts.get("id") or "telemetry_default@v1")

    # Only known schemas are allowed; unknown => safe default.
    if sid == "telemetry_default@v1":
        schema = _default_schema()
        schema.validate()
        return schema

    schema = _default_schema()
    schema.validate()
    return schema
