from __future__ import annotations


SYNONYM_CLUSTERS: dict[str, tuple[str, ...]] = {
    "gateway_role": ("gateway", "router", "dispatcher"),
    "packet_role": ("packet", "bundle", "payload", "envelope"),
    "watch_role": ("watch", "monitor", "inspector"),
    "value_role": ("score", "value", "utility", "priority"),
}
