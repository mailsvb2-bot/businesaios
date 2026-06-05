from __future__ import annotations

"""Canonical self-heal primitives for the Telegram outbound queue.

This module is the single ownership point for:
- self-heal state transitions
- suppression event emission
- best-effort backlog purge helpers

Legacy imports from ``_outbound_selfheal`` are preserved as thin re-exports.
"""

import threading
import time
from dataclasses import dataclass
from typing import Any, Optional
from collections.abc import Callable

from interfaces.telegram.outbound.outbound_self_heal_ops import (
    maybe_self_heal,
    purge_backlog,
)


@dataclass
class SelfHealConfig:
    enabled: bool = False
    cooldown_ns: int = 60_000_000_000
    on_sla: bool = True
    on_qsize: bool = True
    on_drops: bool = False
    purge_enabled: bool = True
    purge_max_items: int = 10_000
    purge_blacklist: tuple[str, ...] = ("marketing", "bulk", "analytics")
    purge_whitelist: tuple[str, ...] = ("ux", "system", "payments", "ack")


class SelfHealController:
    """Thread-safe self-heal state machine."""

    def __init__(
        self,
        config: SelfHealConfig,
        emit: Callable[[str, dict], None] | None = None,
    ) -> None:
        self._cfg = config
        self._emit = emit or (lambda _et, _pl: None)
        self._suppressed_until_ns: int = 0
        self._purge_requested: bool = False
        self._purge_lock = threading.Lock()

    def is_suppressed(self) -> bool:
        if not self._cfg.enabled:
            return False
        return time.monotonic_ns() < self._suppressed_until_ns

    def take_purge_request(self) -> bool:
        if not self._cfg.enabled or not self._cfg.purge_enabled:
            return False
        if not self._purge_requested:
            return False
        if not self._purge_lock.acquire(blocking=False):
            return False
        try:
            if not self._purge_requested:
                return False
            self._purge_requested = False
            return True
        finally:
            self._purge_lock.release()

    def maybe_trigger(
        self,
        *,
        now_ns: int,
        cond_sla: bool,
        cond_drop: bool,
        cond_q: bool,
        reason: str,
        qsize: int,
        ux_p95_wait: float,
        dropped: int,
    ) -> None:
        maybe_self_heal(
            enabled=self._cfg.enabled,
            cond_sla=cond_sla,
            cond_drop=cond_drop,
            cond_q=cond_q,
            on_sla=self._cfg.on_sla,
            on_qsize=self._cfg.on_qsize,
            on_drops=self._cfg.on_drops,
            now_ns=now_ns,
            cooldown_ns=self._cfg.cooldown_ns,
            suppressed_until_ns=self._suppressed_until_ns,
            purge_enabled=self._cfg.purge_enabled,
            set_suppressed_until=self._set_suppressed_until,
            request_purge=self._request_purge,
            emit=self._emit,
            reason=reason,
            qsize=qsize,
            ux_p95_wait=ux_p95_wait,
            dropped=dropped,
        )

    def _set_suppressed_until(self, value: int) -> None:
        self._suppressed_until_ns = int(value)

    def _request_purge(self) -> None:
        self._purge_requested = True


__all__ = [
    "SelfHealConfig",
    "SelfHealController",
    "maybe_self_heal",
    "purge_backlog",
]
