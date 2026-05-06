from __future__ import annotations

from decimal import Decimal
from typing import Any


def build_decision_payload(
    *,
    finance_input,
    forecast,
    advisory,
    liquidity_path,
    scenario_explanation: str,
    allocation_explanation: str,
    liquidity_explanation: str,
    board_summary: dict[str, Any],
    trace_bundle: dict[str, Any],
    assumption_records,
    objective: str,
) -> dict[str, Any]:
    return {
        "tenant_id": finance_input.tenant_id,
        "correlation_id": finance_input.correlation_id,
        "objective": objective,
        "forecast_version": forecast.assumptions_version,
        "selected_scenario": advisory.selected_scenario,
        "runway_months": str(advisory.runway_months),
        "liquidity_tail": [str(x) for x in liquidity_path[-3:]],
        "channel_allocation": {k: str(v) for k, v in advisory.channel_allocation.items()},
        "guard_codes": list(advisory.guard_codes),
        "scenario_scores": {k: str(v) for k, v in advisory.scenario_scores.items()},
        "scenario_rejections": {k: list(v) for k, v in advisory.rejection_reasons.items()},
        "allocation_rationale": list(advisory.allocation_rationale),
        "evidence_trail": list(advisory.evidence_trail),
        "assumption_audit": [
            {
                "key": item.key,
                "old_value": str(item.old_value) if item.old_value is not None else None,
                "new_value": str(item.new_value),
                "actor": item.actor,
            }
            for item in assumption_records
        ],
        "explanations": {
            "scenario": scenario_explanation,
            "allocation": allocation_explanation,
            "liquidity": liquidity_explanation,
        },
        "traces": trace_bundle,
        "board_summary": {
            key: ({sub_key: str(sub_value) for sub_key, sub_value in value.items()} if isinstance(value, dict) else value)
            for key, value in board_summary.items()
        },
        "source_snapshot_id": finance_input.metadata.get("economics_snapshot_id"),
        "source": "core.economics -> core.finance.strategic -> core.ai.decision_core",
        "advisory_only": True,
    }


def min_liquidity_tail(liquidity_path) -> Decimal:
    return min(liquidity_path, default=Decimal("0"))
