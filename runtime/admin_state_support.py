from __future__ import annotations

from runtime._internal.effects_domains.admin_pricing_effects import (
    build_pricing_change_payload as build_pricing_change_payload,
    emit_pricing_change_event as emit_pricing_change_event,
    emit_pricing_reset as emit_pricing_reset,
)
from runtime.lazy_namespace import build_owner_namespace

__getattr__, __dir__, _OWNER_EXPORTS = build_owner_namespace(
    __name__,
    "runtime._internal.effects_domains.admin_state_support",
    exports=(
        "answer_callback_if_needed",
        "emit_toggle_event",
        "emit_admin_notification_event",
        "send_optional_notification",
        "perform_admin_toggle",
        "apply_pricing_change_effect",
        "reject_pricing_change_effect",
        "request_pricing_change_effect",
    ),
)

__all__ = [
    *_OWNER_EXPORTS,
    "build_pricing_change_payload",
    "emit_pricing_change_event",
    "emit_pricing_reset",
]
