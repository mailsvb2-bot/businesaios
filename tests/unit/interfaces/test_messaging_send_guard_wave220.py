import pytest

from interfaces.messaging._shared.send_guard import guarded_send
from runtime.execution.messaging_execution_path_lock import MessagingExecutionPathLockError


def test_guarded_send_requires_canonical_entrypoint():
    with pytest.raises(MessagingExecutionPathLockError):
        guarded_send(caller="not.allowed", send_fn=lambda **kwargs: kwargs)


def test_guarded_send_allows_canonical_entrypoint():
    out = guarded_send(
        caller="runtime.execution.decision_execution_service",
        send_fn=lambda **kwargs: {"ok": True, **kwargs},
        x=1,
    )
    assert out["ok"] is True
    assert out["x"] == 1
