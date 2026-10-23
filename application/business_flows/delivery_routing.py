"""Customer delivery-route selection and status projection (port of donor application/control
helpers). Pure: works over connection, managed-bot and identity records that are already
tenant-scoped. When a shared Telegram connection is missing, it returns a ``connection_proposed``
fact and creates nothing. Credentials appear only as a vault reference, never as secret values.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CONTROL_BOT_CREDENTIAL_REFERENCE = "vault:telegram/control_bot"
NATIVE_PLATFORMS = ("telegram", "vk", "max")


@dataclass(frozen=True)
class Route:
    connection: dict[str, Any]
    identity: dict[str, Any]
    facts: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class DeliveryCounts:
    customers: int
    programs: int
    dispatch_pending: int
    dispatch_sent: int
    dispatch_attention: int


def shared_telegram_connection(connections: list[dict[str, Any]], bot_id: int) -> tuple[dict[str, Any], tuple]:
    ext = str(int(bot_id))
    for c in connections:
        if (
            c.get("platform") == "telegram"
            and c.get("type") == "telegram_shared_bot"
            and str(c.get("external_account_id")) == ext
        ):
            if c.get("status") == "active":
                return c, ()
            return {**c, "status": "active"}, ({"step": "connection_activated", "connection_id": c["id"]},)
    proposed = {
        "id": f"shared-telegram:{ext}",
        "platform": "telegram",
        "type": "telegram_shared_bot",
        "external_account_id": ext,
        "status": "active",
        "credential_ref": CONTROL_BOT_CREDENTIAL_REFERENCE,
        "permissions": ("send_message", "send_media"),
    }
    return proposed, ({"step": "connection_proposed", **proposed},)


def managed_telegram_connection(
    connections: list[dict[str, Any]], managed_bots: list[dict[str, Any]]
) -> dict[str, Any] | None:
    by_id = {c["id"]: c for c in connections if c.get("platform") == "telegram" and c.get("status") == "active"}
    rows = sorted(
        (
            b
            for b in managed_bots
            if b.get("platform") == "telegram" and b.get("status") == "active" and b.get("connection_id") in by_id
        ),
        key=lambda b: (str(b.get("created_at", "")), str(b.get("id", ""))),
    )
    if not rows:
        return None
    if len(rows) != 1:
        raise ValueError("business must have exactly one active managed Telegram bot")
    return by_id[rows[0]["connection_id"]]


def preferred_telegram_connection(connections, managed_bots, bot_id: int) -> tuple[dict[str, Any], tuple]:
    managed = managed_telegram_connection(connections, managed_bots)
    return (managed, ()) if managed is not None else shared_telegram_connection(connections, bot_id)


def single_active_native_connection(connections: list[dict[str, Any]], platform: str) -> dict[str, Any] | None:
    active = [c for c in connections if c.get("platform") == platform and c.get("status") == "active"]
    if len(active) > 1:
        raise ValueError(f"multiple active {platform} connections require explicit channel selection")
    return active[0] if active else None


def preferred_customer_delivery_route(identities, connections, managed_bots, bot_id: int) -> Route:
    """Most recently contacted active Telegram/VK/MAX identity that has a usable connection."""
    live = [i for i in identities if i.get("status", "active") == "active" and i.get("platform") in NATIVE_PLATFORMS]
    live.sort(key=lambda i: str(i.get("id", "")))
    live.sort(
        key=lambda i: str(i.get("last_contact_at") or i.get("updated_at") or i.get("created_at") or ""), reverse=True
    )
    for ident in live:
        if ident["platform"] == "telegram":
            conn, facts = preferred_telegram_connection(connections, managed_bots, bot_id)
            return Route(conn, ident, facts)
        conn = single_active_native_connection(connections, ident["platform"])
        if conn is not None:
            return Route(conn, ident)
    raise ValueError("customer has no active Telegram, VK or MAX identity with an active business connection")


def connection_statuses(connections: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Status projection without credential metadata."""
    ordered = sorted(connections, key=lambda c: (str(c.get("created_at", "")), str(c.get("id", ""))))
    return [(str(c["platform"]), str(c["status"])) for c in ordered]


def count(rows: list[dict[str, Any]], *statuses: str) -> int:
    return sum(1 for r in rows if not statuses or r.get("status") in statuses)


def delivery_summary(*, customers, programs, outbox) -> DeliveryCounts:
    return DeliveryCounts(
        count(customers, "active"),
        count(programs, "active"),
        count(outbox, "pending", "retry", "sending"),
        count(outbox, "sent"),
        count(outbox, "dead"),
    )
