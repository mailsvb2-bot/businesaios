from __future__ import annotations
from typing import Iterable
from execution.strategy.planner_state_contract import StrategicGoalRecord
CANON_PORTFOLIO_ALLOCATOR = True
class PortfolioAllocator:
    _HORIZON_WEIGHT = {
        'today': 1.00,
        'week': 0.94,
        'month': 0.88,
        'quarter': 0.82,
    }
    @staticmethod
    def _memory_bonus(record: StrategicGoalRecord) -> float:
        memory = dict(record.planning_memory or {})
        economic_signal = max(-1.0, min(1.0, float(memory.get('economic_signal_peak') or 0.0)))
        spend_pressure = max(0.0, min(1.0, float(memory.get('spend_pressure_peak') or 0.0)))
        route_confidence = max(0.0, min(1.0, float(memory.get('route_confidence_peak') or 0.0)))
        route_stability = max(0.0, min(1.0, float(memory.get('route_stability_score') or 0.0)))
        focus_mode_stability = max(0.0, min(1.0, float(memory.get('focus_mode_stability_score') or 0.0)))
        verified_success_streak = max(0, int(memory.get('verified_success_streak') or 0))
        focus_mode = str(memory.get('last_focus_mode') or '')
        blocked_runs = int(memory.get('blocked_runs') or 0)
        stalled_runs = int(memory.get('stalled_runs') or 0)
        bonus = (economic_signal * 0.18) + (route_confidence * 0.08) + (route_stability * 0.10) + (focus_mode_stability * 0.05) - (spend_pressure * 0.16)
        bonus += min(0.12, verified_success_streak * 0.03)
        if focus_mode == 'scale_verified_route':
            bonus += 0.08
        elif focus_mode == 'verify_before_scale':
            bonus += 0.03
        elif focus_mode == 'retry_carefully':
            bonus -= 0.04
        bonus -= min(0.10, blocked_runs * 0.02)
        bonus -= min(0.08, stalled_runs * 0.01)
        return bonus
    def advisory_score(self, *, record: StrategicGoalRecord, base_score: float) -> float:
        if record.status == 'completed' or record.blocked:
            return -1.0
        horizon_bonus = self._HORIZON_WEIGHT.get(str(record.planning_horizon or 'week'), 0.90)
        dependency_penalty = min(0.25, 0.05 * len(record.dependencies))
        dependency_state = dict(record.metadata.get("dependency_analysis") or {})
        dependency_ready = bool(dependency_state.get("dependency_ready", not record.dependencies))
        unmet_dependencies = tuple(str(x) for x in (dependency_state.get("missing_dependencies") or ()) if str(x).strip())
        progress_penalty = min(0.35, max(0.0, float(record.progress_score)) * 0.30)
        budget_bonus = min(0.18, max(0.0, float(record.budget_weight) - 1.0) * 0.10)
        priority_pressure = ((float(record.priority) / 100.0) * 0.12) + ((float(record.urgency) / 100.0) * 0.12)
        memory_bonus = self._memory_bonus(record)
        if not dependency_ready:
            dependency_penalty = min(1.20, dependency_penalty + 0.55 + (0.20 * len(unmet_dependencies or record.dependencies or ())))
        score = (base_score * horizon_bonus) + budget_bonus + priority_pressure + memory_bonus - dependency_penalty - progress_penalty
        if not dependency_ready:
            score = min(score, base_score * 0.35)
        return round(score, 6)
    def build_diagnostics(self, *, ranked_records: Iterable[StrategicGoalRecord], base_scores: dict[str, float]) -> dict[str, dict[str, float | str | bool]]:
        diagnostics: dict[str, dict[str, float | str | bool]] = {}
        for record in ranked_records:
            diagnostics[record.goal_id] = {
                'planning_horizon': record.planning_horizon,
                'base_score': round(float(base_scores.get(record.goal_id, 0.0)), 6),
                'portfolio_score': self.advisory_score(record=record, base_score=float(base_scores.get(record.goal_id, 0.0))),
                'dependency_ready': bool(dict(record.metadata.get('dependency_analysis') or {}).get('dependency_ready', not record.dependencies)),
                'last_focus_mode': str(dict(record.planning_memory or {}).get('last_focus_mode') or ''),
                'last_preferred_route_key': str(dict(record.planning_memory or {}).get('last_preferred_route_key') or ''),
                'economic_signal_peak': float(dict(record.planning_memory or {}).get('economic_signal_peak') or 0.0),
                'route_stability_score': float(dict(record.planning_memory or {}).get('route_stability_score') or 0.0),
                'verified_success_streak': int(dict(record.planning_memory or {}).get('verified_success_streak') or 0),
            }
        return diagnostics
