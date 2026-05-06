from __future__ import annotations

from runtime.execution.messaging_execution_path_lock import assert_messaging_execution_entrypoint


def guarded_send(*, caller: str, send_fn, **kwargs):
    assert_messaging_execution_entrypoint(str(caller or ""))
    return send_fn(**kwargs)
