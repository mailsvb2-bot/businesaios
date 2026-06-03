from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

from config.scoring_behavior_policy import DEFAULT_PLANNER_MEMORY_POLICY, PlannerMemoryPolicy

CANON_PLANNER_MEMORY = True
def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)

def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)
def _safe_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(x) for x in value if str(x).strip())
    if value:
        return (str(value),)
    return ()
@dataclass(frozen=True)
class PlannerMemorySummary:
    observed_runs: int = 0
    successful_runs: int = 0
    stalled_runs: int = 0
    blocked_runs: int = 0
    completion_ratio_peak: float = 0.0
    economic_signal_peak: float = 0.0
    spend_pressure_peak: float = 0.0
    route_confidence_peak: float = 0.0
    verified_success_streak: int = 0
    route_stability_score: float = 0.0
    focus_mode_stability_score: float = 0.0
    last_next_mode: str = ""
    last_reason: str = ""
    last_verification_status: str = ""
    last_preferred_route_key: str = ""
    last_focus_mode: str = ""
    recent_modes: tuple[str, ...] = ()
    recent_focus_modes: tuple[str, ...] = ()
    evidence_only: bool = True
    must_not_issue_decision: bool = True
    def to_dict(self) -> dict[str, Any]:
        return {
            "observed_runs": int(self.observed_runs),
            "successful_runs": int(self.successful_runs),
            "stalled_runs": int(self.stalled_runs),
            "blocked_runs": int(self.blocked_runs),
            "completion_ratio_peak": float(self.completion_ratio_peak),
            "economic_signal_peak": float(self.economic_signal_peak),
            "spend_pressure_peak": float(self.spend_pressure_peak),
            "route_confidence_peak": float(self.route_confidence_peak),
            "verified_success_streak": int(self.verified_success_streak),
            "route_stability_score": float(self.route_stability_score),
            "focus_mode_stability_score": float(self.focus_mode_stability_score),
            "last_next_mode": self.last_next_mode,
            "last_reason": self.last_reason,
            "last_verification_status": self.last_verification_status,
            "last_preferred_route_key": self.last_preferred_route_key,
            "last_focus_mode": self.last_focus_mode,
            "recent_modes": list(self.recent_modes),
            "recent_focus_modes": list(self.recent_focus_modes),
            "evidence_only": True,
            "must_not_issue_decision": True,
        }
@dataclass(frozen=True)
class PlannerMemory:
    max_recent_modes: int = 5
    policy: PlannerMemoryPolicy = field(default_factory=lambda: DEFAULT_PLANNER_MEMORY_POLICY)
    _memory_key: str = field(default="planning_memory", init=False, repr=False)
    def summarize_metadata(self, *, metadata: Mapping[str, Any] | None) -> PlannerMemorySummary:
        payload = _safe_dict(metadata)
        memory = _safe_dict(payload.get(self._memory_key))
        recent_modes = _safe_tuple(memory.get("recent_modes"))
        recent_focus_modes = _safe_tuple(memory.get("recent_focus_modes"))
        return PlannerMemorySummary(
            observed_runs=max(0, _safe_int(memory.get("observed_runs"), default=0)),
            successful_runs=max(0, _safe_int(memory.get("successful_runs"), default=0)),
            stalled_runs=max(0, _safe_int(memory.get("stalled_runs"), default=0)),
            blocked_runs=max(0, _safe_int(memory.get("blocked_runs"), default=0)),
            completion_ratio_peak=max(0.0, min(1.0, _safe_float(memory.get("completion_ratio_peak"), default=0.0))),
            economic_signal_peak=max(-1.0, min(1.0, _safe_float(memory.get("economic_signal_peak"), default=0.0))),
            spend_pressure_peak=max(0.0, min(1.0, _safe_float(memory.get("spend_pressure_peak"), default=0.0))),
            route_confidence_peak=max(0.0, min(1.0, _safe_float(memory.get("route_confidence_peak"), default=0.0))),
            verified_success_streak=max(0, _safe_int(memory.get("verified_success_streak"), default=0)),
            route_stability_score=max(0.0, min(1.0, _safe_float(memory.get("route_stability_score"), default=0.0))),
            focus_mode_stability_score=max(0.0, min(1.0, _safe_float(memory.get("focus_mode_stability_score"), default=0.0))),
            last_next_mode=str(memory.get("last_next_mode") or ""),
            last_reason=str(memory.get("last_reason") or ""),
            last_verification_status=str(memory.get("last_verification_status") or ""),
            last_preferred_route_key=str(memory.get("last_preferred_route_key") or ""),
            last_focus_mode=str(memory.get("last_focus_mode") or ""),
            recent_modes=recent_modes,
            recent_focus_modes=recent_focus_modes,
        )
    def _extract_adaptive_strategy(self, *, feedback: Mapping[str, Any] | None) -> dict[str, Any]:
        fb = _safe_dict(feedback)
        direct = _safe_dict(fb.get("strategy_advisory"))
        if direct:
            return direct
        adaptive = _safe_dict(fb.get("adaptive_optimization"))
        return _safe_dict(adaptive.get("strategy_advisory"))
    def _economic_signal(self, *, feedback: Mapping[str, Any] | None) -> tuple[float, float]:
        fb = _safe_dict(feedback)
        revenue_outcome = _safe_dict(fb.get("revenue_outcome"))
        economic = _safe_dict(fb.get("economic"))
        revenue_delta = _safe_float(revenue_outcome.get("delta"), default=economic.get("revenue_delta") or fb.get("revenue_delta") or 0.0)
        cost = max(0.0, _safe_float(economic.get("cost"), default=fb.get("cost") or 0.0))
        denominator = cost if cost > 0.0 else max(1.0, abs(revenue_delta))
        roi_ratio = revenue_delta / denominator if denominator > 0.0 else 0.0
        spend_pressure = min(1.0, cost / max(1.0, cost + max(revenue_delta, 0.0) + 1.0))
        return max(-1.0, min(1.0, roi_ratio)), spend_pressure
    def apply_feedback(
        self,
        *,
        metadata: Mapping[str, Any] | None,
        feedback_view: Mapping[str, Any] | None,
        feedback: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        payload = dict(metadata or {})
        summary = self.summarize_metadata(metadata=payload)
        fbv = _safe_dict(feedback_view)
        fb = _safe_dict(feedback)
        strategy_advisory = self._extract_adaptive_strategy(feedback=fb)
        next_mode = str(fbv.get("next_mode") or "")
        reason = str(fbv.get("reason") or fb.get("verification_status") or "")
        completion_ratio = max(summary.completion_ratio_peak, max(0.0, min(1.0, _safe_float(fbv.get("completion_ratio"), default=0.0))))
        economic_signal, spend_pressure = self._economic_signal(feedback=fb)
        observed_runs = summary.observed_runs + 1
        successful_runs = summary.successful_runs + (1 if bool(fbv.get("achieved")) else 0)
        blocked_runs = summary.blocked_runs + (1 if bool(fbv.get("blocked")) else 0)
        stalled_modes = {"replan", "continue", "verify_and_close"}
        stalled_runs = summary.stalled_runs + (1 if next_mode in stalled_modes and not bool(fbv.get("achieved")) else 0)
        recent_modes = tuple(list(summary.recent_modes + ((next_mode,) if next_mode else ()))[: self.max_recent_modes])
        focus_mode = str(strategy_advisory.get("focus_mode") or "")
        recent_focus_modes = tuple(list(summary.recent_focus_modes + ((focus_mode,) if focus_mode else ()))[: self.max_recent_modes])
        route_keys = tuple(str(x) for x in (strategy_advisory.get("preferred_routes") or ()) if str(x).strip())
        preferred_route_key = str(strategy_advisory.get("preferred_route_key") or (route_keys[0] if route_keys else ""))
        route_confidence = min(1.0, self.policy.route_confidence_base + (self.policy.route_confidence_per_route_bonus * len(route_keys))) if preferred_route_key else 0.0
        verified = str(fb.get("verification_status") or "").strip().lower() == "verified"
        success_streak = 0
        if verified and bool(fbv.get("achieved")):
            success_streak = summary.verified_success_streak + 1
        elif verified:
            success_streak = max(summary.verified_success_streak, 1)
        route_stability_score = summary.route_stability_score
        if preferred_route_key:
            same_route = preferred_route_key == summary.last_preferred_route_key
            same_focus_mode = focus_mode and focus_mode == summary.last_focus_mode
            if same_route:
                route_stability_score = min(1.0, max(route_stability_score, self.policy.route_stability_same_route_floor) + self.policy.route_stability_same_route_bonus)
            elif summary.last_preferred_route_key:
                route_stability_score = max(self.policy.route_stability_changed_route_floor, route_stability_score * self.policy.route_stability_changed_route_multiplier)
            else:
                route_stability_score = max(route_stability_score, self.policy.route_stability_first_route_floor)
            if same_focus_mode:
                route_stability_score = min(1.0, route_stability_score + self.policy.route_stability_same_focus_mode_bonus)
        else:
            route_stability_score = max(0.0, route_stability_score * self.policy.route_stability_no_route_multiplier)
        focus_mode_stability_score = summary.focus_mode_stability_score
        if focus_mode:
            if focus_mode == summary.last_focus_mode:
                focus_mode_stability_score = min(1.0, max(focus_mode_stability_score, self.policy.focus_mode_same_floor) + self.policy.focus_mode_same_bonus)
            elif summary.last_focus_mode:
                focus_mode_stability_score = max(self.policy.focus_mode_changed_floor, focus_mode_stability_score * self.policy.focus_mode_changed_multiplier)
            else:
                focus_mode_stability_score = max(focus_mode_stability_score, self.policy.focus_mode_first_floor)
        else:
            focus_mode_stability_score = max(0.0, focus_mode_stability_score * self.policy.focus_mode_missing_multiplier)
        payload[self._memory_key] = {
            "observed_runs": observed_runs,
            "successful_runs": successful_runs,
            "blocked_runs": blocked_runs,
            "stalled_runs": stalled_runs,
            "completion_ratio_peak": completion_ratio,
            "economic_signal_peak": max(summary.economic_signal_peak, economic_signal),
            "spend_pressure_peak": max(summary.spend_pressure_peak, spend_pressure),
            "route_confidence_peak": max(summary.route_confidence_peak, route_confidence),
            "verified_success_streak": success_streak,
            "route_stability_score": route_stability_score,
            "focus_mode_stability_score": focus_mode_stability_score,
            "last_next_mode": next_mode,
            "last_reason": reason,
            "last_verification_status": str(fb.get("verification_status") or ""),
            "last_preferred_route_key": preferred_route_key,
            "last_focus_mode": focus_mode,
            "recent_modes": list(recent_modes),
            "recent_focus_modes": list(recent_focus_modes),
            "evidence_only": True,
            "must_not_issue_decision": True,
        }
        return payload
