"""User role segmentation (product UX).

Roles:
  - owner: business owner / primary decision maker
  - marketer: marketing operator / agency
  - operator: internal operator / assistant

Role is derived from user settings (transport-agnostic).
This is intentionally dumb and explicit.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

UserRole = Literal["owner", "marketer", "operator"]


@dataclass(frozen=True)
class UserRoleInfo:
    role: UserRole

    @staticmethod
    def from_settings(settings: Mapping[str, Any] | None) -> UserRoleInfo:
        if not isinstance(settings, Mapping):
            return UserRoleInfo("owner")
        raw = str(settings.get("user:role") or "").strip().lower()
        if raw in {"owner", "marketer", "operator"}:
            return UserRoleInfo(raw)  # type: ignore[arg-type]
        return UserRoleInfo("owner")


# One permission contract for verified Telegram roles.
PERMISSIONS = frozenset({
    "connect", "business_read", "customers", "sales", "operations", "marketing",
    "analytics", "payments", "autopilot", "ads_apply", "business_manage", "administration",
})
ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "platform_admin": PERMISSIONS,
    "admin": PERMISSIONS,
    "owner": PERMISSIONS - {"administration"},
    "operator": frozenset({"connect", "operations", "autopilot"}),
    "marketer": frozenset({"connect", "marketing", "analytics", "autopilot", "ads_apply"}),
    "guest": frozenset({"connect"}),
}
ROLE_PERMISSIONS["marketing"] = ROLE_PERMISSIONS["marketer"]
GRANTABLE_ROLES = frozenset({"admin", "owner", "operator", "marketer", "marketing"})
_ROLE_PRIORITY = ("owner", "marketer", "marketing", "operator")


def effective_role(*, is_platform_admin: bool, roles: Any = ()) -> str:
    granted = {str(role).strip().lower() for role in (roles or ())}
    if is_platform_admin or "admin" in granted:
        return "platform_admin"
    role = next((r for r in _ROLE_PRIORITY if r in granted), "guest")
    return "marketer" if role == "marketing" else role


def permissions_for(*, is_platform_admin: bool, roles: Any = ()) -> frozenset[str]:
    granted = {str(role).strip().lower() for role in (roles or ())}
    if is_platform_admin:
        granted.add("platform_admin")
    allowed = set(ROLE_PERMISSIONS["guest"])
    for role in granted:
        allowed.update(ROLE_PERMISSIONS.get(role, ()))
    return frozenset(allowed)


def has_permission(ctx: Any, permission: str) -> bool:
    if permission not in PERMISSIONS:
        return False
    return permission in permissions_for(
        is_platform_admin=bool(getattr(ctx, "is_admin", False)),
        roles=getattr(ctx, "roles", ()) or (),
    )


_COCKPIT_PERMISSIONS = (
    (("menu",), "business_read"),
    (("customers", "customer", "cust-"), "customers"),
    (("sales", "work"), "sales"),
    (("growth-an", "growth-report", "growth-now"), "analytics"),
    (("growth", "ladder"), "marketing"),
    (("money", "payments", "pay-", "prices"), "payments"),
    (("bookings", "bk-", "calendar", "today", "events", "ev-"), "operations"),
)


def cockpit_permission(callback: str) -> str:
    screen = str(callback or "").removeprefix("cpm:").split(":", 1)[0]
    for prefixes, permission in _COCKPIT_PERMISSIONS:
        if any(screen == prefix or (prefix.endswith("-") and screen.startswith(prefix))
               for prefix in prefixes):
            return permission
    if screen.startswith("sales-"):
        return "sales"
    return "business_manage"


_GATED_CALLBACKS = (
    (("autopilot:", "profit_sprint:"), "autopilot"),
    (("ads:apply",), "ads_apply"),
    (("ceo:run",), "business_manage"),  # executing the AI-director plan is an owner decision
    (("ceo:", "growth:"), "analytics"),
)
_GATED_COMMANDS = {
    "/autopilot": "autopilot", "/ceo": "analytics",
    "/growth": "analytics", "/ads_apply": "ads_apply",
}


def required_permission(*, callback_data: str = "", cmd: str = "") -> str | None:
    value = str(callback_data or "")
    permission = next((perm for prefixes, perm in _GATED_CALLBACKS
                       if value.startswith(prefixes)), None)
    if permission is None and value.startswith("cpm:"):
        permission = cockpit_permission(value)
    return permission if permission is not None else _GATED_COMMANDS.get(str(cmd or ""))
