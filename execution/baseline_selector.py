from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from execution.canonical_governance_decision import canonical_baseline_selection_decision


CANON_HEADLESS_BASELINE_SELECTOR = True


@dataclass(frozen=True)
class BaselineSelector:
    """
    Picks the best promotable run from a set of candidate records.

    Governance only. Never affects execution.
    """

    promotion_gate: Any
    run_selector: Any

    def choose(self, *, records: list[dict[str, Any]]) -> dict[str, Any] | None:
        selected, _decision = self.choose_with_decision(records=records)
        return selected

    def choose_with_decision(self, *, records: list[dict[str, Any]], baseline_name: str = '') -> tuple[dict[str, Any] | None, dict[str, Any]]:
        ranked = self.run_selector.rank_runs(records=records)
        ranked_payload = [
            {
                'run_id': item.run_id,
                'goal_score': float(item.goal_score),
                'completed': bool(item.completed),
                'stop_reason': str(item.stop_reason),
                'rank': int(item.rank),
            }
            for item in ranked
        ]
        by_id = {str(record.get("run_id") or ""): record for record in records}

        selected_record = None
        selected_gate_decision = None
        for item in ranked:
            record = by_id.get(item.run_id)
            if record is None:
                continue
            decision = self.promotion_gate.evaluate(record=record)
            if decision.approved:
                selected_record = record
                selected_gate_decision = decision
                break
        return selected_record, canonical_baseline_selection_decision(
            baseline_name=baseline_name,
            selected_record=selected_record,
            ranked_candidates=ranked_payload,
            promotion_decision=selected_gate_decision,
        )


__all__ = [
    "CANON_HEADLESS_BASELINE_SELECTOR",
    "BaselineSelector",
]
