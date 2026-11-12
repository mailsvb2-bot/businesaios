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

    @property
    def tenant_id(self) -> str:
        return str(getattr(self.state, "tenant_id", "") or "")

    @property
    def chat_id(self) -> str:
        session = dict(getattr(self.state, "session", {}) or {})
        user = dict(getattr(self.state, "user", {}) or {})
        return str(session.get("chat_id") or session.get("messaging_chat_id")
                   or session.get("telegram_chat_id") or user.get("telegram_chat_id")
                   or getattr(self.state, "user_id", "") or "")

    @property
    def bot_username(self) -> str:
        product = getattr(self.state, "product", {}) or {}
        return str(product.get("bot_username") or "") if isinstance(product, dict) else ""
