from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from kernel.world_state import WorldStateV1


@dataclass(frozen=True)
class TelegramCtx:
    """Pre-parsed Telegram-relevant view of the WorldState.

    Keep this small and explicit: it is what makes policy logic readable and testable.
    """

    state: WorldStateV1

    # session / ingress
    text: str
    cmd: str | None
    args: str
    callback_data: str
    callback_query_id: str | None

    # user
    settings: dict[str, Any]
    city: str
    moods: list[Any]
    admin_metrics: dict[str, Any]
    is_admin: bool
    roles: list[str]
    perms: list[str]
    is_superadmin: bool

    # realtime state / pricing
    realtime_state: dict[str, Any]
    pricing_suggestions: dict[str, int]

    # economy
    full_access: bool
    pay_status: str
    selected_tariff: dict[str, Any]

    # marketing
    marketing_variants: dict[str, dict[str, str]]
    marketing_seed: str
    # marketing uplift stats (bandit priors), read-only
    # {step_key: {"a": {"alpha":..,"beta":..}, "b": {...}}}
    marketing_bandit: dict[str, dict[str, dict[str, float]]]

    # Business Autopilot dashboards (read-only, computed in read-model)
    autopilot_dashboard: dict[str, Any] = field(default_factory=dict)


_SCOPE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def _scope_id(value: Any) -> str:
    raw = str(value or "").strip()
    return raw if _SCOPE_ID.fullmatch(raw) else ""


@dataclass(frozen=True)
class PolicyScope:
    """Single immutable business scope taken from the trusted WorldState."""
    tenant_id: str
    product_id: str
    business_id: str

    @property
    def has_product(self) -> bool:
        return bool(self.tenant_id and self.product_id)

    @property
    def has_business(self) -> bool:
        return bool(self.has_product and self.business_id)


def policy_scope(ctx: Any) -> PolicyScope:
    state = getattr(ctx, "state", None)
    product = getattr(state, "product", None)
    product = product if isinstance(product, dict) else {}
    tenant = _scope_id(getattr(state, "tenant_id", ""))
    return PolicyScope(
        tenant_id="" if tenant == "default" else tenant,
        product_id=_scope_id(product.get("product_id")),
        business_id=_scope_id(product.get("business_id")),
    )


def scoped_active_plans(ctx: Any) -> list[dict[str, Any]]:
    scope = policy_scope(ctx)
    if not scope.has_product:
        return []
    from core.plans import active_plans

    return list(active_plans(tenant_id=scope.tenant_id, product_id=scope.product_id))


def scoped_plan(ctx: Any, plan_id: int) -> dict[str, Any] | None:
    try:
        target = int(plan_id)
    except (TypeError, ValueError):
        return None
    return next((row for row in scoped_active_plans(ctx)
                 if int(row.get("plan_id") or 0) == target), None)


def operator_flag(ctx: Any, name: str) -> bool:
    meta = getattr(getattr(ctx, "state", None), "meta", None)
    flags = meta.get("operator_flags") if isinstance(meta, dict) else None
    return isinstance(flags, dict) and flags.get(name) is True


def trusted_sales_business_scope(ctx: TelegramCtx, *, owner: bool = True) -> dict[str, str]:
    """Verified ingress takes priority; owner choice is executor-validated state."""
    business_id = policy_scope(ctx).business_id
    chosen = ctx.settings.get("sales:business") if owner and not business_id and isinstance(ctx.settings, dict) else None
    if not business_id and isinstance(chosen, dict):
        business_id = _scope_id(chosen.get("business_id"))
    return {"business_id": business_id} if business_id else {}
