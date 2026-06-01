from __future__ import annotations

"""Telegram runner (orchestration only).

Hard invariants:
- No decisions outside DecisionCore.
- No side-effects outside RuntimeExecutor.
- No direct SDK/network imports.

This runner is intentionally thin.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

from core.observability.silent import swallow
from interfaces.telegram.runner_components import build_runner_components
from interfaces.telegram.runner_loop import handle_idle_poll, poll_updates, run_periodic_loops

logger = logging.getLogger(__name__)


@dataclass
class TelegramRunnerConfig:
    poll_timeout_s: int = 30
    poll_limit: int = 50
    reconcile_every_s: int = 30
    reconcile_window_min: int = 30
    idle_sleep_s: float = 0.2

    ml_enabled: bool = True
    ml_train_every_s: int = 3600
    ml_monitor_every_s: int = 60

    def __post_init__(self) -> None:
        # sanitize
        def _i(v, d):
            try:
                return int(v)
            except Exception:
                return int(d)

        def _f(v, d):
            try:
                return float(v)
            except Exception:
                return float(d)

        self.poll_timeout_s = max(1, min(60, _i(self.poll_timeout_s, 30)))
        self.poll_limit = max(1, min(100, _i(self.poll_limit, 50)))
        self.reconcile_every_s = max(5, min(3600, _i(self.reconcile_every_s, 30)))
        self.reconcile_window_min = max(1, min(24 * 60, _i(self.reconcile_window_min, 30)))
        self.idle_sleep_s = max(0.0, min(5.0, _f(self.idle_sleep_s, 0.2)))
        self.ml_train_every_s = max(60, min(24 * 3600, _i(self.ml_train_every_s, 3600)))
        self.ml_monitor_every_s = max(10, min(3600, _i(self.ml_monitor_every_s, 60)))


class TelegramRunner:
    def __init__(
        self,
        *,
        decide_fn: Any,
        execute_fn: Any,
        event_store: Any,
        event_log: Any,
        payment_outbox: Any = None,
        learning_job: Any = None,
        config: TelegramRunnerConfig | None = None,
    ):
        self._decide = decide_fn
        self._execute = execute_fn
        self._event_store = event_store
        self._event_log = event_log
        self._payment_outbox = payment_outbox
        self._learning_job = learning_job
        self._cfg = config or TelegramRunnerConfig()

        components = build_runner_components(
            decide_fn=self._decide,
            execute_fn=self._execute,
            event_store=self._event_store,
            event_log=self._event_log,
            payment_outbox=self._payment_outbox,
            learning_job=self._learning_job,
            cfg=self._cfg,
        )
        self._poller = components["poller"]
        self._enricher = components["enricher"]
        self._processor = components["processor"]
        self._reconcile = components["reconcile"]
        self._payment_jobs = components["payment_jobs"]
        self._ml = components["ml"]
        self._offer_outcome = components["offer_outcome"]

        self._retry_delay = 1.0

        # Loop health (best-effort). Used by /health endpoint.
        # Keys are stable loop names; values are timestamps in ms.
        self._loop_health: dict[str, dict[str, Any]] = {
            "ml": {"last_tick_ms": 0, "last_ok_ms": 0, "last_err_ms": 0, "last_err": None},
            "reconcile": {"last_tick_ms": 0, "last_ok_ms": 0, "last_err_ms": 0, "last_err": None},
            "payment_jobs": {"last_tick_ms": 0, "last_ok_ms": 0, "last_err_ms": 0, "last_err": None},
            "offer_outcome": {"last_tick_ms": 0, "last_ok_ms": 0, "last_err_ms": 0, "last_err": None},
        }

    def health_loops(self) -> dict[str, dict[str, Any]]:
        """Best-effort loop tick timestamps for operators.

        Read-only snapshot. Never raises.
        """
        try:
            out: dict[str, dict[str, Any]] = {}
            for k, v in (self._loop_health or {}).items():
                out[str(k)] = dict(v)
            return out
        except Exception:
            return {}

    def run_forever(self) -> None:
        last_idle_log_ms: int = 0
        last_ok_poll_ms: int = 0
        last_loop_err_ms: dict[str, int] = {}
        while True:
            run_periodic_loops(
                ml=self._ml,
                reconcile=self._reconcile,
                payment_jobs=self._payment_jobs,
                offer_outcome=self._offer_outcome,
                loop_health=self._loop_health,
                last_loop_err_ms=last_loop_err_ms,
                event_log=self._event_log,
            )

            updates, self._retry_delay, polled_at_ms = poll_updates(poller=self._poller, retry_delay=self._retry_delay)
            if polled_at_ms:
                last_ok_poll_ms = polled_at_ms
            should_continue, last_idle_log_ms = handle_idle_poll(
                updates=updates,
                idle_sleep_s=float(self._cfg.idle_sleep_s),
                last_idle_log_ms=last_idle_log_ms,
                last_ok_poll_ms=last_ok_poll_ms,
                poller=self._poller,
            )
            if should_continue:
                continue

            for upd in updates:
                self._processor.handle_update(upd)
