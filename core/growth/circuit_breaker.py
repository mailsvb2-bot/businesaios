from __future__ import annotations

"""Ads circuit breaker.

Goal: protect against runaway automation and external platform instability.

This is intentionally small and deterministic:
  - it does NOT create alternative write paths
  - it only blocks writes, never forces them

State is in-memory (per process). In multi-node deployments, this should be
backed by event_store aggregation or a shared store.
"""

from dataclasses import dataclass
import time
from typing import Dict


@dataclass
class BreakerConfig:
    window_s: int = 600  # 10 minutes
    max_failures: int = 3
    cooloff_s: int = 900  # 15 minutes


@dataclass
class BreakerState:
    failures: int = 0
    first_failure_ts: float = 0.0
    blocked_until_ts: float = 0.0


class CircuitBreaker:
    def __init__(self, *, cfg: BreakerConfig | None = None) -> None:
        self._cfg = cfg or BreakerConfig()
        self._state: Dict[str, BreakerState] = {}

    def should_block(self, *, key: str) -> bool:
        st = self._state.get(key)
        if not st:
            return False
        now = time.time()
        if st.blocked_until_ts > now:
            return True
        # auto-reset after window
        if st.first_failure_ts and (now - st.first_failure_ts) > self._cfg.window_s:
            self._state.pop(key, None)
            return False
        return False

    def record_success(self, *, key: str) -> None:
        # success heals breaker
        self._state.pop(key, None)

    def record_failure(self, *, key: str) -> None:
        now = time.time()
        st = self._state.get(key)
        if not st:
            st = BreakerState(failures=0, first_failure_ts=now, blocked_until_ts=0.0)
            self._state[key] = st

        # reset if outside window
        if st.first_failure_ts and (now - st.first_failure_ts) > self._cfg.window_s:
            st.failures = 0
            st.first_failure_ts = now

        st.failures += 1
        if st.failures >= self._cfg.max_failures:
            st.blocked_until_ts = now + self._cfg.cooloff_s
