from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CANON_DECISION_CONTRACTS = True
DECISION_CONTRACT_V2_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class DecisionContractV2:
    business_id: str
    goal_id: str | None
    world_state_version: str
    agent_id: str
    model_profile: str
    decision_strategy: str
    alternatives: tuple[dict[str, Any], ...] = ()
    selected_option: dict[str, Any] = field(default_factory=dict)
    rationale: dict[str, Any] = field(default_factory=dict)
    confidence: float | None = None
    expected_value: float | None = None
    risk: Any = None
    created_at: int = 0
    do_nothing_baseline: Any = None
    schema_version: int = DECISION_CONTRACT_V2_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "business_id": self.business_id,
            "goal_id": self.goal_id,
            "world_state_version": self.world_state_version,
            "agent_id": self.agent_id,
            "model_profile": self.model_profile,
            "decision_strategy": self.decision_strategy,
            "alternatives": [dict(item) for item in self.alternatives],
            "selected_option": dict(self.selected_option),
            "rationale": dict(self.rationale),
            "confidence": self.confidence,
            "expected_value": self.expected_value,
            "risk": self.risk,
            "created_at": int(self.created_at),
            "do_nothing_baseline": self.do_nothing_baseline,
            "schema_version": int(self.schema_version),
        }


@dataclass(frozen=True)
class Decision:
    decision_id: str
    issuer_id: str
    issued_at_ms: int
    expires_at_ms: int
    policy_id: str
    action: str
    payload: dict
    snapshot_id: str
    state_hash: str
    correlation_id: str
    state_schema_version: int
    action_schema_version: int
    envelope_version: int = 1
    contract_v2: dict[str, Any] | None = None


@dataclass(frozen=True)
class DecisionEnvelope:
    decision: Decision
    payload_hash: str
    signature: str
    kid: str
    # Optional self-driving rollout metadata (pure; defaults preserve behavior)
    policy_version: str | None = None
    rollout_group: str | None = None
    canary_flag: bool = False
    envelope_version: int = 1


__all__ = [
    "CANON_DECISION_CONTRACTS",
    "DECISION_CONTRACT_V2_SCHEMA_VERSION",
    "Decision",
    "DecisionContractV2",
    "DecisionEnvelope",
]
