from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.ai.decision import Decision, DecisionEnvelope
from kernel.decision_crypto import signed_envelope_from_decision
from kernel.decisioning.route_contract import EXPECTED_ISSUER_ID, DecisionRouteViolation


@dataclass(frozen=True)
class DecisionCommand:
    decision_id: str
    correlation_id: str
    issuer_id: str
    action: str
    payload: dict[str, Any] = field(default_factory=dict)
    snapshot_id: str = ''
    state_hash: str = ''
    policy_id: str = 'decision-command'
    issued_at_ms: int = 0
    expires_at_ms: int = 0
    state_schema_version: int = 1
    action_schema_version: int = 1
    envelope_version: int = 1

    def validate(self) -> None:
        if not str(self.decision_id or '').strip():
            raise DecisionRouteViolation('decision_id is required')
        if not str(self.correlation_id or '').strip():
            raise DecisionRouteViolation('correlation_id is required')
        if not str(self.issuer_id or '').strip():
            raise DecisionRouteViolation('issuer_id is required')
        if self.issuer_id != EXPECTED_ISSUER_ID:
            raise DecisionRouteViolation(f"issuer_id must be {EXPECTED_ISSUER_ID!r}")
        if not str(self.action or '').strip():
            raise DecisionRouteViolation('action is required')
        if not isinstance(self.payload, dict):
            raise DecisionRouteViolation('payload must be dict')

    def to_envelope(self) -> DecisionEnvelope:
        raise DecisionRouteViolation(
            'unsigned DecisionCommand.to_envelope() is forbidden; use to_signed_envelope(keyring)'
        )

    def to_signed_envelope(self, keyring: Any) -> DecisionEnvelope:
        self.validate()
        decision = Decision(
            decision_id=self.decision_id,
            issuer_id=self.issuer_id,
            issued_at_ms=int(self.issued_at_ms),
            expires_at_ms=int(self.expires_at_ms),
            policy_id=self.policy_id,
            action=self.action,
            payload=dict(self.payload),
            snapshot_id=self.snapshot_id,
            state_hash=self.state_hash,
            correlation_id=self.correlation_id,
            state_schema_version=int(self.state_schema_version),
            action_schema_version=int(self.action_schema_version),
            envelope_version=int(self.envelope_version),
        )
        return signed_envelope_from_decision(decision=decision, keyring=keyring)
