from runtime.guard import RuntimeGuard
from survival.controller import SurvivalMode, SurvivalVerdict


class _Survival:
    def evaluate(self):
        return SurvivalVerdict(mode=SurvivalMode.NORMAL, allow_execution=True, reason="ok")


class _Ledger:
    def __init__(self):
        self.done = set()
    def try_mark_executed(self, env):
        return True
    def is_executed(self, decision_id: str) -> bool:
        return decision_id in self.done
    def already_executed(self, decision_id: str) -> bool:
        return decision_id in self.done
    def mark_executed(self, decision_id: str) -> None:
        self.done.add(decision_id)
    def verify_chain(self) -> bool:
        return True


class _Verifier:
    def verify(self, envelope):
        return True


class _Envelope:
    decision_id = "d1"
    action = "noop"


def test_reference_mode_initializes_contract_fields_safely():
    guard = RuntimeGuard(_Survival(), _Ledger(), _Verifier())
    verdict = guard.verify_and_lock(_Envelope())
    assert verdict.allow_execution is True
    guard.commit(_Envelope())
