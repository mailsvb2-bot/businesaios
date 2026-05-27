from __future__ import annotations

from interfaces.common.registry_capability_contract import build_registry_entry

CONNECTORS = {
    "call_tracking": build_registry_entry(
        name="call_tracking",
        status="not_implemented",
        supports_dry_run=True,
    ),
    "email": build_registry_entry(
        name="email",
        status="implemented",
        read=True,
        write=True,
        verify=True,
        supports_dry_run=True,
        supports_idempotency=True,
        production_ready=False,
        reversible=False,
        requires_human_approval=False,
        action_types=("send_message@v1", "send_email", "reply_to_inquiry", "request_review"),
    ),
    "sms": build_registry_entry(
        name="sms",
        status="not_implemented",
        supports_dry_run=True,
        action_types=("send_message",),
    ),
    "telegram": build_registry_entry(
        name="telegram",
        status="not_implemented",
        supports_dry_run=True,
        action_types=("send_message",),
    ),
    "whatsapp": build_registry_entry(
        name="whatsapp",
        status="not_implemented",
        supports_dry_run=True,
        action_types=("send_message",),
    ),
}

__all__ = ["CONNECTORS"]
