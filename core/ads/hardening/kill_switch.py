"""Ads kill switch.

Single flag to disable ALL ads operations system-wide.
Respects the single-source-of-truth principle: this module is the ONLY
place that decides whether ads operations proceed.

Patch 10.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from config.env_flags import env_bool

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KillSwitchState:
    enabled: bool
    reason: Optional[str] = None
    since_ms: int = 0


class AdsKillSwitch:
    """Centralized ads kill switch.

    Priority (highest first):
      1. ENV: ADS_KILL_SWITCH=1 → all ads disabled
      2. Runtime flag set by governance
      3. Default: ads enabled (reads only; writes gated separately)
    """

    def __init__(self) -> None:
        self._runtime_kill: bool = False
        self._runtime_reason: str = ""
        self._runtime_since_ms: int = 0

    def kill(self, reason: str = "manual") -> None:
        self._runtime_kill = True
        self._runtime_reason = str(reason)
        self._runtime_since_ms = int(time.time() * 1000)
        logger.warning("ads_kill_switch=ACTIVATED reason=%s", reason)

    def restore(self) -> None:
        self._runtime_kill = False
        self._runtime_reason = ""
        logger.info("ads_kill_switch=RESTORED")

    @property
    def state(self) -> KillSwitchState:
        # ENV override (highest priority)
        if env_bool("ADS_KILL_SWITCH", False):
            return KillSwitchState(
                enabled=False,
                reason="env:ADS_KILL_SWITCH=1",
                since_ms=0,
            )
        # Runtime flag
        if self._runtime_kill:
            return KillSwitchState(
                enabled=False,
                reason=self._runtime_reason,
                since_ms=self._runtime_since_ms,
            )
        return KillSwitchState(enabled=True)

    @property
    def is_enabled(self) -> bool:
        return self.state.enabled

    def assert_enabled(self) -> None:
        s = self.state
        if not s.enabled:
            raise RuntimeError(f"ADS_KILLED: {s.reason}")
