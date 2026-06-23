from __future__ import annotations

from interfaces.messaging._shared import send_outbound
from interfaces.messaging._shared.send_guard import guarded_send
from runtime.execution.messaging_execution_path_lock import CANON_MESSAGING_EXECUTION_ENTRYPOINT


def send_raw(*, cfg, msg):
    payload = getattr(msg, "payload", {}) if hasattr(msg, "payload") else {}
    caller = ""
    if isinstance(payload, dict):
        caller = str(payload.get("execution_entrypoint", "") or "").strip()
    return guarded_send(caller=caller or CANON_MESSAGING_EXECUTION_ENTRYPOINT, send_fn=send_outbound, cfg=cfg, msg=msg)
