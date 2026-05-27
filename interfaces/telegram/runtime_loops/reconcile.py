from __future__ import annotations

"""Periodic reconcile loop for payments.

Runner-owned orchestration only.
"""

import time
from dataclasses import dataclass
from typing import Any

from interfaces.telegram.runtime.telegram_runtime_worldstate_builder import build_system_world_state
from runtime.platform.config.env_flags import env_str


@dataclass
class ReconcileConfig:
    every_s: int = 30


class PaymentsReconcileLoop:
    def __init__(self, *, decide_fn: Any, execute_fn: Any, cfg: ReconcileConfig):
        self._decide = decide_fn
        self._execute = execute_fn
        self._cfg = cfg
        self._last_ms: int = 0

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    def tick(self) -> None:
        now_ms = self._now_ms()
        if (now_ms - self._last_ms) < int(self._cfg.every_s * 1000):
            return
        self._last_ms = now_ms
        ws = build_system_world_state(
            purpose="payments_reconcile",
            user_timezone=env_str("SYSTEM_TZ", "Europe/Amsterdam"),
            now_ms=now_ms,
        )
        env = self._decide(ws)
        self._execute(env)
