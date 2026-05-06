from __future__ import annotations

from dataclasses import dataclass


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


def _contains_secret_keys(obj) -> bool:
    SUSPECT = ["SECRET", "TOKEN", "KEY", "PASSWORD"]
    if isinstance(obj, dict):
        for k, v in obj.items():
            if any(s in str(k).upper() for s in SUSPECT):
                return True
            if _contains_secret_keys(v):
                return True
    elif isinstance(obj, (list, tuple)):
        return any(_contains_secret_keys(x) for x in obj)
    return False


def _decision_envelope_verify(self) -> None:
    from kernel.decision_crypto import assert_envelope_signature_surface

    assert_envelope_signature_surface(self)
    if _contains_secret_keys(self.decision.payload):
        raise RuntimeError("Secret leak into Decision Ring payload")
    if self.decision.expires_at_ms < self.decision.issued_at_ms:
        raise RuntimeError("Invalid timestamps")


# Bind as method without changing dataclass definition shape
DecisionEnvelope.verify = _decision_envelope_verify  # type: ignore[attr-defined]
