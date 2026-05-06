from __future__ import annotations

from interfaces.messaging._shared import send_outbound
from interfaces.messaging._shared.send_guard import guarded_send


def send_raw(*, cfg, msg):
    caller = getattr(msg, "payload", {}).get("execution_entrypoint", "") if hasattr(msg, "payload") else ""
    return guarded_send(caller=caller, send_fn=send_outbound, cfg=cfg, msg=msg)
