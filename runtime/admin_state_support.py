from __future__ import annotations

from runtime.lazy_namespace import build_owner_namespace

__getattr__, __dir__, __all__ = build_owner_namespace(
    __name__,
    "runtime._internal.effects_domains.admin_state_support",
    exports=(
        "answer_callback_if_needed",
        "emit_toggle_event",
        "emit_admin_notification_event",
        "send_optional_notification",
        "perform_admin_toggle",
        "build_pricing_change_payload",
        "apply_pricing_change_effect",
        "emit_pricing_change_event",
        "emit_pricing_reset",
        "reject_pricing_change_effect",
        "request_pricing_change_effect",
    ),
)
