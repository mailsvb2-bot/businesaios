from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from core.ads.rl.policy_store import PolicyStore
from core.governance.evaluators.profit_metrics import ProfitMetricsService


@dataclass(frozen=True)
class Suggestion:
    ok: bool
    reason: str
    action: Dict[str, Any] | None = None
    policy_version: int | None = None


class RLSuggester:
    def __init__(self, *, store: PolicyStore, profit_metrics: ProfitMetricsService) -> None:
        self._store = store
        self._pm = profit_metrics

    def suggest(self, *, tenant_id: str, current_daily_budget_minor: int | None = None) -> Suggestion:
        pol = self._store.get_latest(tenant_id=str(tenant_id))
        if not pol:
            return Suggestion(ok=False, reason="no_policy")
        m = int(pol.params.get("budget_multiplier_x1000") or 1000)
        if current_daily_budget_minor is None:
            baseline = int(self._pm.today_spend_minor(tenant_id=str(tenant_id)))
            if baseline >= 10**11:
                return Suggestion(ok=False, reason="spend_ledger_uncertain")
            current_daily_budget_minor = max(0, baseline)
        proposed = int(int(current_daily_budget_minor) * m / 1000)
        action = {
            "kind": "ads_budget_multiplier",
            "multiplier_x1000": m,
            "baseline_daily_budget_minor": int(current_daily_budget_minor),
            "proposed_daily_budget_minor": int(proposed),
        }
        return Suggestion(ok=True, reason="ok", action=action, policy_version=int(pol.version))
