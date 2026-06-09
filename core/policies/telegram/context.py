from __future__ import annotations

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
