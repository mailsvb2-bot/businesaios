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
        self.items = []

    def execute_recovery(self, env):
        self.items.append(env)


class _Outbox:
    def __init__(self):
        self.rows = [{"tenant_id": "tenant-1", "decision_id": "d-1", "status": "pending"}]
        self.delivered = []
        self.dead = []

    def list_claimable(self, *, limit: int = 100):
        return list(self.rows[:limit])

    def mark_delivered(self, decision_id: str):
        self.delivered.append(decision_id)

    def move_to_dead_letter(self, decision_id: str):
        self.dead.append(decision_id)



def test_recover_pending_terminal_noop_marks_item_terminal_without_reexecution() -> None:
    env = object()
    outbox = _Outbox()
    recovered = recover_pending(executor=_Executor("noop"), outbox=outbox, archive=_Archive({"d-1": env}), limit=10)
    assert recovered == 0
    assert outbox.delivered == ["d-1"]



def test_recover_pending_quarantine_moves_item_to_dead_letter_without_reexecution() -> None:
    env = object()
    outbox = _Outbox()
    recovered = recover_pending(executor=_Executor("quarantine"), outbox=outbox, archive=_Archive({"d-1": env}), limit=10)
    assert recovered == 0
    assert outbox.dead == ["d-1"]
