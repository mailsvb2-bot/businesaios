from __future__ import annotations

from runtime.messaging_policy_alert_subscriptions.subscription_parser import parse_subscription


def parse_subscription_list(value, *, tenant_id: str) -> tuple:
    if not isinstance(value, list | tuple):
        return ()
    out = []
    for item in value:
        parsed = parse_subscription(item, tenant_id=tenant_id)
        if parsed is not None:
            out.append(parsed)
    return tuple(out)
