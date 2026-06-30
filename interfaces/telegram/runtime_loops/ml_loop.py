"""Self-driving ML loop scheduling.

Runner only triggers LearningJob methods; it never deploys directly.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

@dataclass
class MLLooopConfig:
    enabled: bool = True
    train_every_s: int = 3600
    monitor_every_s: int = 60


class MLLearningLoop:
    def __init__(self, *, learning_job: Any, cfg: MLLooopConfig):
        self._job = learning_job
        self._cfg = cfg
        self._last_train_ms = 0
        self._last_monitor_ms = 0

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    def tick(self) -> None:
        if not self._cfg.enabled or self._job is None:
            return
        now = self._now_ms()
        if self._last_train_ms == 0 or (now - self._last_train_ms) >= int(self._cfg.train_every_s * 1000):
            self._last_train_ms = now
            self._job.run_once()
        if self._last_monitor_ms == 0 or (now - self._last_monitor_ms) >= int(self._cfg.monitor_every_s * 1000):
            self._last_monitor_ms = now
            self._job.monitor_and_maybe_rollback()
