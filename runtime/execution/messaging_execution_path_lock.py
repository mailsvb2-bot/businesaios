from __future__ import annotations

CANON_MESSAGING_EXECUTION_PATH_LOCK = True
CANON_MESSAGING_EXECUTION_ENTRYPOINT = "runtime.execution.decision_execution_service"


class MessagingExecutionPathLockError(RuntimeError):
    pass


def assert_messaging_execution_entrypoint(caller: str) -> None:
    if str(caller or "") != CANON_MESSAGING_EXECUTION_ENTRYPOINT:
        raise MessagingExecutionPathLockError(
            f"messaging_execution_requires_canonical_entrypoint:{caller}"
        )
