from __future__ import annotations

from typing import Any, Mapping

from execution.budget_posture_contract import BudgetPostureRecommendation


CANON_ADAPTIVE_BUDGET_POLICY = True


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _text(value: object) -> str:
    return str(value or '').strip()


class AdaptiveBudgetPolicy:
    def normalize_posture(self, payload: Mapping[str, Any] | None) -> BudgetPostureRecommendation:
        data = _safe_dict(payload)
        posture = _text(data.get('posture') or data.get('recommended_budget_posture') or 'neutral') or 'neutral'
        reasons = tuple(str(x) for x in (data.get('reasons') or []) if str(x).strip())
        cost_multiplier = 1.0
        total_multiplier = 1.0
        outbound_multiplier = 1.0
        publication_multiplier = 1.0
        if posture == 'tighten':
            cost_multiplier = 0.85
            total_multiplier = 0.90
            outbound_multiplier = 0.90
            publication_multiplier = 0.90
        elif posture == 'expand_carefully':
            cost_multiplier = 1.10
            total_multiplier = 1.08
        return BudgetPostureRecommendation(
            posture=posture,
            cost_multiplier=float(data.get('cost_multiplier') or cost_multiplier),
            total_budget_multiplier=float(data.get('total_budget_multiplier') or total_multiplier),
            outbound_multiplier=float(data.get('outbound_multiplier') or outbound_multiplier),
            publication_multiplier=float(data.get('publication_multiplier') or publication_multiplier),
            confidence=float(data.get('confidence') or 0.0),
            reasons=reasons,
            metadata={k: v for k, v in data.items() if k not in {'posture', 'recommended_budget_posture', 'reasons'}},
        )

    def apply(self, *, posture_payload: Mapping[str, Any] | None, limits: Mapping[str, Any]) -> dict[str, Any]:
        posture = self.normalize_posture(posture_payload)
        updated = dict(limits)
        if 'max_run_cost' in updated:
            updated['max_run_cost'] = float(updated['max_run_cost']) * posture.cost_multiplier
        if 'max_total_cost' in updated:
            updated['max_total_cost'] = float(updated['max_total_cost']) * posture.total_budget_multiplier
        if 'max_outbound_total' in updated:
            updated['max_outbound_total'] = int(float(updated['max_outbound_total']) * posture.outbound_multiplier)
        if 'max_publications_total' in updated:
            updated['max_publications_total'] = int(float(updated['max_publications_total']) * posture.publication_multiplier)
        updated['budget_posture'] = posture.to_dict()
        return updated


__all__ = ['CANON_ADAPTIVE_BUDGET_POLICY', 'AdaptiveBudgetPolicy']
