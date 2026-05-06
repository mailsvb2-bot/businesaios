from __future__ import annotations

from collections.abc import Mapping as AbcMapping
from typing import Any

from execution.agi_reasoning_contract import AGIGoalCandidate, AGIReasoningSummary
from execution.autonomy_learning_context_policy import AutonomyLearningContextPolicy
from execution.goal_family_classifier import GoalFamilyClassifier
from execution.opportunity_detector import OpportunityDetector
from execution.strategy.strategic_planner import StrategicPlanner
from execution.strategy_support_policy import StrategySupportPolicy


CANON_AGI_REASONING_ENGINE = True
AGI_REASONING_MAX_SIGNALS = 12
AGI_REASONING_MAX_CANDIDATES = 8
AGI_REASONING_MAX_HINTS = 8


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, AbcMapping):
        return dict(value)
    return {}


def _safe_list(value: object) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return []


def _text(value: object) -> str:
    return str(value or "").strip()


def _priority_rank(priority: str) -> int:
    token = _text(priority).lower()
    if token == "high":
        return 3
    if token == "medium":
        return 2
    if token == "low":
        return 1
    return 0


def _normalize_world_state_mapping(state: Any) -> dict[str, Any]:
    if isinstance(state, AbcMapping):
        mapping = dict(state)
    else:
        mapping = {
            "tenant_id": getattr(state, "tenant_id", ""),
            "meta": dict(getattr(state, "meta", {}) or {}),
            "economy": dict(getattr(state, "economy", {}) or {}),
            "product": dict(getattr(state, "product", {}) or {}),
            "user": dict(getattr(state, "user", {}) or {}),
            "session": dict(getattr(state, "session", {}) or {}),
            "observations": {},
            "timestamp_ms": getattr(state, "timestamp_ms", 0),
            "user_id": getattr(state, "user_id", None),
        }

    meta = _safe_dict(mapping.get("meta"))
    session = _safe_dict(mapping.get("session"))
    observations = _safe_dict(mapping.get("observations"))
    meta_observations = _safe_dict(meta.get("observations"))
    merged_observations = {
        **session,
        **meta_observations,
        **observations,
    }
    mapping["meta"] = meta
    mapping["session"] = session
    mapping["observations"] = merged_observations
    return mapping


class AGIReasoningEngine:
    def __init__(
        self,
        *,
        opportunity_detector: OpportunityDetector | None = None,
        goal_family_classifier: GoalFamilyClassifier | None = None,
        strategy_support_policy: StrategySupportPolicy | None = None,
        strategic_planner: StrategicPlanner | None = None,
        learning_context_policy: AutonomyLearningContextPolicy | None = None,
    ) -> None:
        self._opportunity_detector = opportunity_detector or OpportunityDetector()
        self._goal_family_classifier = goal_family_classifier or GoalFamilyClassifier()
        self._strategy_support_policy = strategy_support_policy or StrategySupportPolicy()
        self._strategic_planner = strategic_planner or StrategicPlanner()
        self._learning_context_policy = learning_context_policy or AutonomyLearningContextPolicy()

    def build_summary(
        self,
        *,
        state: Any,
        world_snapshot: dict[str, Any] | None = None,
    ) -> AGIReasoningSummary:
        mapping = _normalize_world_state_mapping(state)
        meta = _safe_dict(mapping.get("meta"))
        observations = _safe_dict(mapping.get("observations"))
        business_memory = _safe_dict(meta.get("business_memory_evidence"))
        capability_snapshot = _safe_dict(meta.get("capability_snapshot") or meta.get("runtime_" "capabilities"))
        execution_closed_loop = _safe_dict(meta.get("execution_closed_loop"))

        suppressed_reasons: list[str] = []

        raw_signals = self._opportunity_detector.detect(mapping)
        signals = self._dedupe_signals(raw_signals)
        if len(raw_signals) > len(signals):
            suppressed_reasons.append("duplicate_opportunity_signals_suppressed")

        candidates = self._build_goal_candidates(
            observations=observations,
            business_memory=business_memory,
            signals=signals,
        )
        if len(candidates) > AGI_REASONING_MAX_CANDIDATES:
            suppressed_reasons.append("goal_candidates_capped")

        selected = candidates[0] if candidates else None
        selected_goal = None if selected is None else selected.to_dict()
        selected_goal_text = "" if selected is None else selected.goal
        selected_goal_family = "default" if selected is None else selected.goal_family

        planner_metadata = self._strategic_planner.enrich_metadata(
            goal=selected_goal_text,
            metadata={
                "signal_count": len(signals),
                "world_snapshot_present": bool(world_snapshot),
                "capability_snapshot_present": bool(capability_snapshot),
                "budget_posture": str(execution_closed_loop.get("recommended_budget_posture") or "neutral"),
            },
        )

        raw_hints = self._strategy_support_policy.build_hints(
            goal_family=selected_goal_family,
            feedback=execution_closed_loop,
            metadata=planner_metadata,
        )
        strategy_hints = tuple(hint.to_dict() for hint in raw_hints[:AGI_REASONING_MAX_HINTS])
        if len(raw_hints) > len(strategy_hints):
            suppressed_reasons.append("strategy_hints_capped")

        learning_context = self._learning_context_policy.compose(
            tenant_id=str(mapping.get("tenant_id") or ""),
            business_id=str(meta.get("business_id") or meta.get("project_id") or ""),
            goal_family=selected_goal_family,
            performance_context={
                "recommended_budget_posture": str(
                    execution_closed_loop.get("recommended_budget_posture") or "neutral"
                ),
            },
            capability_context={
                "available_capabilities": sorted(str(key) for key in capability_snapshot.keys()),
                "capability_count": len(capability_snapshot),
            },
            strategy_hints=tuple(strategy_hints),
            retry_profile={},
        ).to_dict()

        explainability = {
            "reasoning_mode": "state_enrichment_only",
            "selected_goal_family": selected_goal_family,
            "selected_goal_present": selected is not None,
            "signal_count": len(signals),
            "candidate_count": len(candidates[:AGI_REASONING_MAX_CANDIDATES]),
            "world_snapshot_present": bool(world_snapshot),
            "no_second_brain": True,
            "decision_owner": "core.ai.decision_core.DecisionCore",
            "contract_owner": "bootstrap.world_model_contract.DecisionWorldModelPort",
        }

        return AGIReasoningSummary(
            selected_goal=selected_goal,
            goal_candidates=tuple(item.to_dict() for item in candidates[:AGI_REASONING_MAX_CANDIDATES]),
            strategy_hints=tuple(strategy_hints),
            planning_horizon=str(planner_metadata.get("planning_horizon") or "week"),
            decomposed_focus=tuple(
                str(x)
                for x in (_safe_list(planner_metadata.get("decomposed_focus")))
                if str(x).strip()
            ),
            world_snapshot=self._compact_world_snapshot(world_snapshot),
            opportunity_signals=tuple(signal.to_dict() for signal in signals[:AGI_REASONING_MAX_SIGNALS]),
            learning_context=learning_context,
            explainability=explainability,
            suppressed_reasons=tuple(suppressed_reasons),
        )

    def _build_goal_candidates(
        self,
        *,
        observations: dict[str, Any],
        business_memory: dict[str, Any],
        signals: tuple[Any, ...],
    ) -> tuple[AGIGoalCandidate, ...]:
        candidates: list[AGIGoalCandidate] = []
        active_goals = [str(x) for x in _safe_list(business_memory.get("active_goals")) if str(x).strip()]

        for idx, goal in enumerate(active_goals):
            candidates.append(
                AGIGoalCandidate(
                    goal_id=f"memory_goal:{idx}",
                    goal=goal,
                    goal_family=self._goal_family_classifier.classify(goal),
                    priority="high",
                    source="business_memory",
                    rationale="Active goal already present in business memory",
                    metadata={"active_goals_count": len(active_goals)},
                )
            )

        signal_to_goal = {
            "conversion_gap": "improve conversion on existing demand",
            "demand_gap": "restore demand generation",
            "execution_instability": "stabilize execution reliability",
            "negative_revenue_trend": "recover revenue trend",
            "goal_gap": "establish one active bounded goal",
        }
        for idx, signal in enumerate(signals):
            payload = signal.to_dict() if hasattr(signal, "to_dict") else _safe_dict(signal)
            signal_type = str(payload.get("signal_type") or "")
            goal = signal_to_goal.get(signal_type)
            if not goal:
                continue
            candidates.append(
                AGIGoalCandidate(
                    goal_id=f"signal_goal:{idx}",
                    goal=goal,
                    goal_family=self._goal_family_classifier.classify(goal),
                    priority=str(payload.get("priority") or "medium"),
                    source="opportunity_detector",
                    rationale=str(payload.get("rationale") or signal_type),
                    metadata={"signal_type": signal_type},
                )
            )

        if not candidates:
            baseline_goal = "maintain safe profit adjusted growth"
            candidates.append(
                AGIGoalCandidate(
                    goal_id="baseline_goal:0",
                    goal=baseline_goal,
                    goal_family=self._goal_family_classifier.classify(baseline_goal),
                    priority="low",
                    source="baseline",
                    rationale="No explicit active goal or opportunity signal found",
                    metadata={"observations_present": bool(observations)},
                )
            )

        ranked = sorted(
            candidates,
            key=lambda item: (_priority_rank(item.priority), item.source == "business_memory"),
            reverse=True,
        )
        return tuple(ranked)

    def _dedupe_signals(self, signals: tuple[Any, ...]) -> tuple[Any, ...]:
        out: list[Any] = []
        seen: set[tuple[str, str, str]] = set()
        for signal in signals:
            payload = signal.to_dict() if hasattr(signal, "to_dict") else _safe_dict(signal)
            key = (
                str(payload.get("signal_type") or ""),
                str(payload.get("title") or ""),
                str(payload.get("rationale") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(signal)
        return tuple(out)

    @staticmethod
    def _compact_world_snapshot(world_snapshot: dict[str, Any] | None) -> dict[str, Any]:
        payload = _safe_dict(world_snapshot)
        if not payload:
            return {}
        out = {
            "snapshot_id": _text(payload.get("snapshot_id")),
            "business_id": _text(payload.get("business_id")),
            "tenant_id": _text(payload.get("tenant_id")),
            "confidence": payload.get("confidence"),
            "status": _text(payload.get("status")),
            "schema_version": _text(payload.get("schema_version")),
        }
        return {key: value for key, value in out.items() if value not in ("", None)}


__all__ = ["CANON_AGI_REASONING_ENGINE", "AGIReasoningEngine"]
