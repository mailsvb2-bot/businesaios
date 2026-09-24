from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from typing import Any

from application.business_goal import BusinessGoalProjector
from application.headless.models import GoalExecutionRequest
from application.memory.business_memory_state_adapter import BusinessMemoryStateAdapter
from application.memory.business_operating_memory import (
    project_business_memory_evidence,
    project_business_memory_profile,
)
from kernel.world_state import WorldStateV1

CANON_HEADLESS_GOAL_MAPPER = True


@dataclass(frozen=True)
class HeadlessGoalStateMapper:
    """
    Thin mapper only.

    It translates a headless goal request into the canonical WorldStateV1.
    It MUST NOT decide actions or rank alternatives.
    CEO participation is encoded only as advisory context in state.meta.
    Business memory is projected strictly as evidence/context, not a second brain.
    """

    business_memory_state_adapter: BusinessMemoryStateAdapter = field(default_factory=BusinessMemoryStateAdapter)
    semantic_snapshot_reader: Any | None = None
    canonical_goal_reader: Any | None = None

    @staticmethod
    def build_canonical_goal_reader(event_store: Any) -> BusinessGoalProjector:
        return BusinessGoalProjector(event_store)

    def to_world_state(
        self,
        *,
        request: GoalExecutionRequest,
        step_index: int,
        previous_feedback: dict[str, Any],
    ) -> WorldStateV1:
        now_ms = int(time.time() * 1000)
        session = {
            "channel": request.channel,
            "command": "headless_goal_execute",
            "text": request.goal,
            "step_index": int(step_index),
        }
        product = {
            "name": request.product_name,
            "region": request.region,
            "business_id": request.business_id,
        }
        ceo_meta = {
            "enabled": bool(request.ceo.enabled),
            "objective": str(request.ceo.objective or request.goal),
            "horizon": str(request.ceo.horizon),
            "risk_level": str(request.ceo.risk_level),
            "mode": str(request.ceo.mode),
            "advisory_only": True,
            "must_not_issue_decision": True,
            "must_not_unlock_effects": True,
        }
        request_meta = dict(request.meta or {})
        canonical_goal: dict[str, Any] = {}
        if request.goal_id is not None:
            if self.canonical_goal_reader is None:
                raise RuntimeError("canonical Goal reader is required when goal_id is provided")
            canonical_goal = dict(
                self.canonical_goal_reader.load_context(
                    tenant_id=request.tenant_id,
                    business_id=request.business_id,
                    goal_id=request.goal_id,
                )
            )
        raw_memory = project_business_memory_evidence(dict(request_meta.get('business_memory') or {}))
        memory_profile = project_business_memory_profile(raw_memory)
        memory_evidence = self.business_memory_state_adapter.to_state_context(raw_memory)
        merged_profile = {**memory_profile, **dict(request.profile or {})}
        meta = {
            **request_meta,
            "headless": True,
            "goal": request.goal,
            "goal_id": request.goal_id,
            "canonical_goal": canonical_goal,
            "profile": merged_profile,
            "signals": list(request.signals or []),
            "constraints": dict(request.constraints or {}),
            "previous_feedback": dict(previous_feedback or {}),
            "ceo": ceo_meta,
            "business_memory": dict(raw_memory),
            "business_memory_evidence": memory_evidence,
        }
        state = WorldStateV1(
            schema_version=1,
            user={
                "user_id": request.user_id,
                "tenant_id": request.tenant_id,
                "region": request.region,
            },
            session=session,
            product=product,
            economy=dict(request.economy or {}),
            timestamp_ms=now_ms,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            meta=meta,
            behavior={
                "goal": request.goal,
                "goal_id": request.goal_id,
                "step_index": int(step_index),
                "strategic_objective": str(request.ceo.objective or request.goal),
            },
            price_constraints=dict(request.constraints or {}) or None,
        )
        if getattr(self.business_memory_state_adapter, "store", None) is not None:
            state = self.business_memory_state_adapter.inject(
                world_state=state,
                tenant_id=request.tenant_id,
                business_id=request.business_id,
            )
        reader = self.semantic_snapshot_reader
        if reader is None:
            return state
        snapshot = reader.load_latest(
            tenant_id=request.tenant_id,
            business_id=request.business_id,
        )
        if snapshot is None:
            return state
        if (
            str(snapshot.tenant_id) != str(request.tenant_id)
            or str(snapshot.business_id) != str(request.business_id)
        ):
            raise ValueError("semantic World Model snapshot scope mismatch")
        if snapshot.semantic_view is None:
            raise ValueError("semantic World Model snapshot is missing semantic_view")
        return replace(state, world_model_semantics=snapshot.semantic_view)


__all__ = ["CANON_HEADLESS_GOAL_MAPPER", "HeadlessGoalStateMapper"]
