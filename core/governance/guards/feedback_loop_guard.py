from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.governance.evaluators.profit_metrics import ProfitMetricsService


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    code: Optional[str] = None
    message: Optional[str] = None


class FeedbackLoopGuard:
    """Blocks runaway budget ramps when profit is non-positive."""

    def __init__(
        self,
        *,
        metrics: ProfitMetricsService,
        lookback_days: int = 3,
        max_budget_increase_pct: int = 10,
        require_positive_profit: bool = True,
    ) -> None:
        self._metrics = metrics
        self._lookback_days = int(lookback_days)
        self._max_inc_pct = int(max_budget_increase_pct)
        self._require_pos = bool(require_positive_profit)

    def check_planned_budget(self, *, tenant_id: str, planned_daily_budget_minor: int) -> GuardDecision:
        planned = int(planned_daily_budget_minor)
        snap = self._metrics.profit_lookback(tenant_id=str(tenant_id), lookback_days=self._lookback_days)
        if (not self._require_pos) or snap.profit_minor > 0:
            return GuardDecision(allowed=True)

        today_spend = int(self._metrics.today_spend_minor(tenant_id=str(tenant_id)))
        if today_spend >= 10**11:
            return GuardDecision(
                allowed=False,
                code="ADS_FEEDBACK_UNCERTAIN_SPEND",
                message="Blocked: spend ledger uncertain (ads_metrics_imported missing/partial).",
            )

        safe_cap = int(today_spend * (100 + self._max_inc_pct) / 100)
        if planned > safe_cap and safe_cap > 0:
            return GuardDecision(
                allowed=False,
                code="ADS_RUNAWAY_FEEDBACK_LOOP",
                message=(
                    f"Blocked budget ramp: profit_minor={snap.profit_minor} over {self._lookback_days}d, "
                    f"planned_daily_budget_minor={planned} > safe_cap_minor={safe_cap} (today_spend_minor={today_spend})."
                ),
            )
        return GuardDecision(allowed=True)
