"""Stable digest for AdsPlan.

We hash (platform, action, payload-json-stable) for each command.
This is used for idempotency keys and audit correlation.

This module is PURE.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def plan_digest(plan: Any) -> str:
    cmds = getattr(plan, "commands", None)
    if not isinstance(cmds, list):
        return "empty"
    items: list[tuple[str, str, str]] = []
    for c in cmds:
        try:
            platform = str(getattr(c, "platform", "") or "")
            action = str(getattr(c, "action", "") or "")
            payload = getattr(c, "payload", {}) or {}
            payload_s = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            items.append((platform, action, payload_s))
        except Exception:
            continue
    raw = "\n".join([f"{p}|{a}|{pl}" for (p, a, pl) in items])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
