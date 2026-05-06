from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True
CANON_BOOT_CLUSTER_FINAL_OWNER = True


from typing import Any

from runtime.world_model import WorldModelBuildInput


_PLACEHOLDER_IDS = {"", "default", "legacy", "none", "null"}


def _normalized_identifier(value: Any, *, unknown: str) -> str:
    text = str(value or "").strip()
    if text.lower() in _PLACEHOLDER_IDS:
        return unknown
    return text or unknown


def build_world_snapshot_input(*, payload: dict[str, Any], now_ms: int) -> WorldModelBuildInput:
    world_state = dict(payload.get("world_state") or payload)
    context = dict(payload.get("context") or {})
    return WorldModelBuildInput(
        tenant_id=_normalized_identifier(world_state.get("tenant_id"), unknown="unknown_tenant"),
        business_id=_normalized_identifier(world_state.get("business_id"), unknown="unknown_business"),
        customer_id=_normalized_identifier(world_state.get("customer_id"), unknown="unknown_customer"),
        product_id=_normalized_identifier(world_state.get("product_id"), unknown="unknown_product"),
        channel=_normalized_identifier(world_state.get("channel"), unknown="unknown_channel"),
        geo=_normalized_identifier(world_state.get("geo"), unknown="unknown_geo"),
        now_ms=int(now_ms),
        correlation_id=str(payload.get("correlation_id") or world_state.get("correlation_id") or ""),
        context=context,
    )
