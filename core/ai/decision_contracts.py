from __future__ import annotations

from dataclasses import dataclass

CANON_DECISION_CONTRACTS = True

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


__all__ = ["CANON_DECISION_CONTRACTS", "Decision", "DecisionEnvelope"]
