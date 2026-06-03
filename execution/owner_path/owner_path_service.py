from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from collections.abc import Mapping
from application.memory.business_operating_memory import project_business_memory_governance_summary
from execution.owner_path.owner_path_contract import OWNER_PATH_STAGES, OwnerPathSnapshot
CANON_OWNER_PATH_SERVICE = True
class FileOwnerPathStore:
    def __init__(self, *, root_dir: Path) -> None:
        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)
    def _path(self, *, tenant_id: str, business_id: str) -> Path:
        safe_tenant = str(tenant_id or "unknown").replace("/", "_")
        safe_business = str(business_id or "unknown").replace("/", "_")
        return self._root_dir / safe_tenant / f"{safe_business}.json"
    def load(self, *, tenant_id: str, business_id: str) -> dict[str, Any]:
        path = self._path(tenant_id=tenant_id, business_id=business_id)
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    def save(self, *, tenant_id: str, business_id: str, payload: Mapping[str, Any]) -> None:
        path = self._path(tenant_id=tenant_id, business_id=business_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(payload or {}), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
class OwnerPathService:
    def __init__(self, *, store: FileOwnerPathStore) -> None:
        self._store = store
    @staticmethod
    def _safe_dict(value: object) -> dict[str, Any]:
        return dict(value) if isinstance(value, Mapping) else {}
    def load_context(self, *, tenant_id: str, business_id: str) -> dict[str, Any]:
        payload = self._store.load(tenant_id=tenant_id, business_id=business_id)
        if not payload:
            stages = {stage: {"present": False, "reason": "not_observed_yet"} for stage in OWNER_PATH_STAGES}
            return OwnerPathSnapshot(tenant_id=tenant_id, business_id=business_id, stages=stages).to_dict()["owner_path"]
        owner_payload = self._safe_dict(payload.get("owner_path"))
        snapshot = OwnerPathSnapshot(
            tenant_id=str(payload.get("tenant_id") or tenant_id),
            business_id=str(payload.get("business_id") or business_id),
            stages={stage: self._safe_dict(owner_payload.get("stages", {}).get(stage)) for stage in OWNER_PATH_STAGES},
            last_action_type=str(payload.get("last_action_type") or ""),
            last_goal=str(payload.get("last_goal") or ""),
            observation_count=int(payload.get("observation_count") or owner_payload.get("observation_count") or 0),
            resumed_from_previous_run=True,
            last_decision_id=str(payload.get("last_decision_id") or owner_payload.get("last_decision_id") or ""),
            last_correlation_id=str(payload.get("last_correlation_id") or owner_payload.get("last_correlation_id") or ""),
            stage_observation_counts={
                stage: int(self._safe_dict(owner_payload.get("stage_observation_counts")).get(stage) or 0)
                for stage in OWNER_PATH_STAGES
            },
        )
        return snapshot.to_dict()["owner_path"]
    def _state_synthesis_stage(self, *, feedback: Mapping[str, Any]) -> dict[str, Any]:
        raw_after_step = self._safe_dict(feedback.get("business_memory_after_step"))
        raw_business_memory = self._safe_dict(feedback.get("business_memory"))
        raw_summary = self._safe_dict(feedback.get("business_memory_summary"))
        summary = project_business_memory_governance_summary(raw_summary or raw_after_step or raw_business_memory)
        present = bool(summary.get("business_profile") or summary.get("active_goals") or raw_after_step or raw_business_memory)
        if raw_summary:
            reason = "business_memory_summary"
        elif raw_after_step:
            reason = "business_memory_after_step"
        elif raw_business_memory:
            reason = "business_memory"
        else:
            reason = "missing"
        return {
            "present": present,
            "reason": reason,
        }

    def update_after_step(self, *, tenant_id: str, business_id: str, goal: str, feedback: Mapping[str, Any] | None) -> dict[str, Any]:
        fb = self._safe_dict(feedback)
        previous_payload = self._store.load(tenant_id=tenant_id, business_id=business_id)
        previous_owner_path = self._safe_dict(previous_payload.get("owner_path"))
        previous_stage_counts = self._safe_dict(previous_owner_path.get("stage_observation_counts"))
        capability_planning = self._safe_dict(fb.get("capability_planning"))
        action_budget = self._safe_dict(fb.get("action_budget_state"))
        goal_eval = self._safe_dict(fb.get("goal_evaluation"))
        adaptive = self._safe_dict(fb.get("adaptive_optimization"))
        stages = {
            "planner": {
                "present": bool(self._safe_dict(fb.get("goal_plan")) or fb.get("goal_score") is not None),
                "reason": "goal_plan_context" if self._safe_dict(fb.get("goal_plan")) else "goal_score",
            },
            "routing": {
                "present": bool(capability_planning),
                "reason": str(capability_planning.get("selected_route") or capability_planning.get("selected_capability") or capability_planning.get("reason") or "missing"),
            },
            "economics": {
                "present": bool(action_budget) or bool(self._safe_dict(fb.get("bounded_autonomy"))),
                "reason": str(action_budget.get("status") or self._safe_dict(fb.get("bounded_autonomy")).get("reason") or "missing"),
            },
            "execution": {
                "present": bool(fb.get("attempted") or fb.get("executed") or fb.get("ok")),
                "reason": "executed" if bool(fb.get("executed")) else "attempted",
            },
            "verification": {
                "present": bool(fb.get("verified")) or str(fb.get("verification_status") or "") in {"verified", "payload_verified"},
                "reason": str(fb.get("verification_status") or ("verified" if bool(fb.get("verified")) else "missing")),
            },
            "state_synthesis": self._state_synthesis_stage(feedback=fb),
            "optimization": {
                "present": bool(adaptive) or bool(self._safe_dict(fb.get("performance_learning"))),
                "reason": str(adaptive.get("noise_reason") or ("performance_learning" if self._safe_dict(fb.get("performance_learning")) else "missing")),
            },
        }
        stage_observation_counts = {
            stage: int(previous_stage_counts.get(stage) or 0) + (1 if bool(dict(stages.get(stage) or {}).get("present")) else 0)
            for stage in OWNER_PATH_STAGES
        }
        snapshot = OwnerPathSnapshot(
            tenant_id=tenant_id,
            business_id=business_id,
            stages=stages,
            last_action_type=str(fb.get("action_type") or fb.get("route_key") or ""),
            last_goal=str(goal or goal_eval.get("goal") or ""),
            observation_count=int(previous_payload.get("observation_count") or previous_owner_path.get("observation_count") or 0) + 1,
            resumed_from_previous_run=bool(previous_payload),
            last_decision_id=str(fb.get("decision_id") or previous_payload.get("last_decision_id") or ""),
            last_correlation_id=str(fb.get("correlation_id") or previous_payload.get("last_correlation_id") or ""),
            stage_observation_counts=stage_observation_counts,
        )
        payload = snapshot.to_dict()
        self._store.save(tenant_id=tenant_id, business_id=business_id, payload=payload)
        return dict(payload.get("owner_path") or {})
