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
    def __init__(self, action: str, error: Exception):
        self._reliability = _Reliability(action)
        self._error = error

    def execute_recovery(self, env):
        raise self._error


class _Outbox:
    def __init__(self):
        self.rows = [{"tenant_id": "tenant-x", "decision_id": "d-1", "status": "pending"}]
        self.dead = []

    def list_claimable(self, *, limit: int = 100):
        return list(self.rows[:limit])

    def claim(self, message_id: str):
        return True

    def move_to_dead_letter(self, decision_id: str):
        self.dead.append(decision_id)


class _EnvWithoutDecision:
    pass



def test_recovery_failure_without_env_decision_uses_item_tenant_and_quarantines() -> None:
    outbox = _Outbox()
    env = _EnvWithoutDecision()
    recovered = recover_pending(
        executor=_Executor("resume", RuntimeError("boom")),
        outbox=outbox,
        archive=_Archive({"d-1": env}),
        limit=10,
    )
    assert recovered == 0
    assert outbox.dead == ["d-1"]
