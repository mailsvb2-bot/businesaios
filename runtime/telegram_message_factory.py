from __future__ import annotations

from runtime.lazy_namespace import build_owner_namespace

__getattr__, __dir__, __all__ = build_owner_namespace(
    __name__,
    "runtime._internal.effects_actions.telegram.messaging_parts.message_factory",
    exports=(
        "resolve_tenant_id",
        "build_message_text",
        "build_message_parse_mode",
        "build_message_reply_markup",
    ),
)
