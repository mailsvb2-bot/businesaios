from __future__ import annotations

from runtime.recovery import recover_pending


class _Archive:
    def __init__(self, mapping):
        self._mapping = dict(mapping)

    def get(self, decision_id: str):
        return self._mapping.get(decision_id)


class _Plan:
    def __init__(self, action: str):
        self.recovery_action = action


class _Reliability:
    def __init__(self, action: str):
        self._action = action

    def plan(self, env):
        return _Plan(self._action)


class _Executor:
    def __init__(self, action: str):
        self._reliability = _Reliability(action)
        self.calls = 0

    def execute_recovery(self, env):
        self.calls += 1
        raise AssertionError('execute_recovery must not run for unknown recovery actions')


class _Outbox:
    def __init__(self):
        self.rows = [{'tenant_id': 'tenant-1', 'decision_id': 'd-1', 'status': 'pending'}]
        self.dead = []

    def list_claimable(self, *, limit: int = 100):
        return list(self.rows[:limit])

    def move_to_dead_letter(self, decision_id: str):
        self.dead.append(decision_id)


class _Env:
    pass


def test_unknown_recovery_action_is_quarantined_and_terminal() -> None:
    outbox = _Outbox()
    executor = _Executor('mystery_action')
    recovered = recover_pending(executor=executor, outbox=outbox, archive=_Archive({'d-1': _Env()}), limit=10)
    assert recovered == 0
    assert executor.calls == 0
    assert outbox.dead == ['d-1']
