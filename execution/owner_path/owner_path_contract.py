from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
CANON_OWNER_PATH_CONTRACT = True
OWNER_PATH_STAGES: tuple[str, ...] = (
    "planner",
    "routing",
    "economics",
    "execution",
    "verification",
    "state_synthesis",
    "optimization",
)
@dataclass(frozen=True)
class OwnerPathSnapshot:
    tenant_id: str
    business_id: str
    stages: dict[str, dict[str, Any]]
    last_action_type: str = ""
    last_goal: str = ""
    observation_count: int = 0
    resumed_from_previous_run: bool = False
    last_decision_id: str = ""
    last_correlation_id: str = ""
    stage_observation_counts: dict[str, int] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]:
        complete = all(bool(dict(self.stages.get(stage) or {}).get("present")) for stage in OWNER_PATH_STAGES)
        return {
            "tenant_id": self.tenant_id,
            "business_id": self.business_id,
            "last_action_type": self.last_action_type,
            "last_goal": self.last_goal,
            "observation_count": int(self.observation_count),
            "resumed_from_previous_run": bool(self.resumed_from_previous_run),
            "last_decision_id": self.last_decision_id,
            "last_correlation_id": self.last_correlation_id,
            "owner_path": {
                "stages": {stage: dict(self.stages.get(stage) or {}) for stage in OWNER_PATH_STAGES},
                "stage_observation_counts": {stage: int(self.stage_observation_counts.get(stage) or 0) for stage in OWNER_PATH_STAGES},
                "stages_complete": complete,
                "present_stage_count": sum(1 for stage in OWNER_PATH_STAGES if bool(dict(self.stages.get(stage) or {}).get("present"))),
                "canonical_stage_order": list(OWNER_PATH_STAGES),
                "observation_count": int(self.observation_count),
                "resumed_from_previous_run": bool(self.resumed_from_previous_run),
                "last_decision_id": self.last_decision_id,
                "last_correlation_id": self.last_correlation_id,
                "evidence_only": True,
                "must_not_issue_decision": True,
                "second_brain_blocked": True,
            },
        }
