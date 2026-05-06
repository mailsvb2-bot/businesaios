from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.decimal_utils import q2


class BoardSummaryBuilder:
    def build(
        self,
        annual_plan: dict[str, Decimal],
        runway_months: Decimal,
        top_risks: list[str],
        *,
        selected_scenario: str | None = None,
        decision_reason: str | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            'annual_plan': annual_plan,
            'runway_months': q2(runway_months),
            'top_risks': tuple(top_risks),
        }
        if selected_scenario is not None:
            payload['selected_scenario'] = selected_scenario
        if decision_reason is not None:
            payload['decision_reason'] = decision_reason
        return payload
