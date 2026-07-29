"""Explicit canonical issuer fixture for decision-gateway E2E tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any


@dataclass
class CapturingDecisionIssuer:
    decision_id: str = "decision-e2e-1"
    correlation_id: str = "correlation-e2e-1"
    captured_states: list[Any] = field(default_factory=list)

    def issue(self, state: Any) -> Any:
        self.captured_states.append(state)
        return SimpleNamespace(
            decision=SimpleNamespace(
                decision_id=self.decision_id,
                correlation_id=self.correlation_id,
                action="observe_only@v1",
                payload={},
            )
        )
