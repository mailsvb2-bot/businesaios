from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from kernel.world_state import WorldStateV1


@dataclass(frozen=True)
class TelegramCtx:
    """Pre-parsed Telegram-relevant view of the WorldState.

    Keep this small and explicit: it is what makes policy logic readable and testable.
    """

    state: WorldStateV1

    # session / ingress
    text: str
    cmd: Optional[str]
    args: str
    callback_data: str
    callback_query_id: Optional[str]

    # user
    settings: Dict[str, Any]
    city: str
    moods: List[Any]
    admin_metrics: Dict[str, Any]
    is_admin: bool
    roles: List[str]
    perms: List[str]
    is_superadmin: bool

    # realtime state / pricing
    realtime_state: Dict[str, Any]
    pricing_suggestions: Dict[str, int]

    # economy
    full_access: bool
    pay_status: str
    selected_tariff: Dict[str, Any]

    # marketing
    marketing_variants: Dict[str, Dict[str, str]]
    marketing_seed: str
    # marketing uplift stats (bandit priors), read-only
    # {step_key: {"a": {"alpha":..,"beta":..}, "b": {...}}}
    marketing_bandit: Dict[str, Dict[str, Dict[str, float]]]

    # Business Autopilot dashboards (read-only, computed in read-model)
    autopilot_dashboard: Dict[str, Any] = field(default_factory=dict)
