from __future__ import annotations

from typing import Any, Mapping

from execution.strategy_hint_contract import StrategyHint


CANON_STRATEGY_SUPPORT_POLICY = True


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


class StrategySupportPolicy:
    def build_hints(self, *, goal_family: str, feedback: Mapping[str, Any] | None = None, metadata: Mapping[str, Any] | None = None) -> tuple[StrategyHint, ...]:
        payload = _safe_dict(feedback)
        meta = _safe_dict(metadata)
        hints: list[StrategyHint] = []
        if goal_family in {'revenue_growth', 'pipeline_growth'}:
            hints.append(StrategyHint('prefer_verified_growth', 0.7, 'growth_family'))
        if payload.get('approval_required') or meta.get('requires_approval'):
            hints.append(StrategyHint('approval_gate_present', 0.8, 'requires_approval'))
        if payload.get('blocked_by_policy'):
            hints.append(StrategyHint('policy_block_recent', 0.9, 'policy_block'))
        if not hints:
            hints.append(StrategyHint('baseline_strategy_support', 0.3, 'default'))
        return tuple(hints)


__all__ = ['CANON_STRATEGY_SUPPORT_POLICY', 'StrategySupportPolicy']
