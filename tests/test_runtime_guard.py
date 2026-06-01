import pytest

from runtime.guard import DecisionEnvelopeRef as DecisionEnvelope
from runtime.guard import RuntimeGuard
from runtime.inmemory_ledger import InMemoryLedger
from survival.controller import SurvivalController, SurvivalMetrics


class AllowAllVerifier:
    def verify(self, envelope: DecisionEnvelope) -> bool:
        return True


class DummyMetrics:
    def get_metrics(self):
        return SurvivalMetrics(
            cashflow=10,
            churn_rate=0,
            error_rate=0,
            runtime_alive=True,
            policy_health=1,
        )


def make_guard():
    survival = SurvivalController(DummyMetrics())
    ledger = InMemoryLedger()
    verifier = AllowAllVerifier()
    return RuntimeGuard(survival, ledger, verifier)


def test_execute_once():
    guard = make_guard()

    env = DecisionEnvelope("1", "pay", "h", "sig")

    guard.verify_and_lock(env)
    guard.commit(env)

    with pytest.raises(RuntimeError):
        guard.verify_and_lock(env)


def test_blocks_when_survival_forbids():
    class DeadMetrics:
        def get_metrics(self):
            return SurvivalMetrics(
                cashflow=10,
                churn_rate=0,
                error_rate=0,
                runtime_alive=False,
                policy_health=1,
            )

    survival = SurvivalController(DeadMetrics())
    guard = RuntimeGuard(survival, InMemoryLedger(), AllowAllVerifier())

    env = DecisionEnvelope("1", "pay", "h", "sig")

    with pytest.raises(RuntimeError):
        guard.verify_and_lock(env)
