from __future__ import annotations

import pytest

from execution.action_catalog import known_action_types
from runtime.guard import DecisionEnvelopeRef, RuntimeGuard
from runtime.inmemory_ledger import InMemoryLedger
from survival.controller import SurvivalController, SurvivalMetrics


class _AllowEverySignature:
    def verify(self, envelope: DecisionEnvelopeRef) -> bool:
        return True


class _HealthyRuntimeMetrics:
    def get_metrics(self) -> SurvivalMetrics:
        return SurvivalMetrics(
            cashflow=10,
            churn_rate=0,
            error_rate=0,
            runtime_alive=True,
            policy_health=1,
        )


def test_every_action_is_rejected_after_the_same_decision_is_committed() -> None:
    cases = 0
    for action_type in known_action_types():
        guard = RuntimeGuard(
            SurvivalController(_HealthyRuntimeMetrics()),
            InMemoryLedger(),
            _AllowEverySignature(),
        )
        envelope = DecisionEnvelopeRef(
            f"decision:{action_type}",
            action_type,
            "payload-hash",
            "signature",
        )
        guard.verify_and_lock(envelope)
        guard.commit(envelope)
        with pytest.raises(RuntimeError):
            guard.verify_and_lock(envelope)
        cases += 1
    assert cases == 43
