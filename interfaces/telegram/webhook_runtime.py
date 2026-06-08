from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

from interfaces.telegram.runner_components import build_runner_components
from interfaces.telegram.runner_loop import run_periodic_loops

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TelegramWebhookConfig:
    secret_token: str
    webhook_path: str = '/telegram/webhook'
    periodic_tick_interval_s: float = 1.0

    def normalized_path(self) -> str:
        path = str(self.webhook_path or '').strip() or '/telegram/webhook'
        if not path.startswith('/'):
            path = '/' + path
        return path


class TelegramWebhookRuntime:
    def __init__(
        self,
        *,
        decide_fn: Any,
        execute_fn: Any,
        event_store: Any,
        event_log: Any,
        payment_outbox: Any = None,
        learning_job: Any = None,
        runner_config: Any = None,
        webhook_config: TelegramWebhookConfig,
    ) -> None:
        self._event_log = event_log
        self._cfg = webhook_config
        components = build_runner_components(
            decide_fn=decide_fn,
            execute_fn=execute_fn,
            event_store=event_store,
            event_log=event_log,
            payment_outbox=payment_outbox,
            learning_job=learning_job,
            cfg=runner_config,
        )
        self._processor = components['processor']
        self._reconcile = components['reconcile']
        self._payment_jobs = components['payment_jobs']
        self._ml = components['ml']
        self._offer_outcome = components['offer_outcome']
        self._loop_health: dict[str, dict[str, Any]] = {
            'ml': {'last_tick_ms': 0, 'last_ok_ms': 0, 'last_err_ms': 0, 'last_err': None},
            'reconcile': {'last_tick_ms': 0, 'last_ok_ms': 0, 'last_err_ms': 0, 'last_err': None},
            'payment_jobs': {'last_tick_ms': 0, 'last_ok_ms': 0, 'last_err_ms': 0, 'last_err': None},
            'offer_outcome': {'last_tick_ms': 0, 'last_ok_ms': 0, 'last_err_ms': 0, 'last_err': None},
        }
        self._last_loop_err_ms: dict[str, int] = {}
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def secret_token(self) -> str:
        return self._cfg.secret_token

    @property
    def webhook_path(self) -> str:
        return self._cfg.normalized_path()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_periodic_loops, name='telegram-webhook-loops', daemon=True)
        self._thread.start()

    def shutdown(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=5.0)
        self._thread = None

    def process_update(self, update: Mapping[str, Any]) -> None:
        self._processor.handle_update(dict(update or {}))

    def health_snapshot(self) -> dict[str, Any]:
        return {
            'webhook_path': self.webhook_path,
            'loops': {key: dict(value) for key, value in self._loop_health.items()},
            'loop_thread_alive': bool(self._thread is not None and self._thread.is_alive()),
        }

    def _run_periodic_loops(self) -> None:
        sleep_s = max(0.1, float(self._cfg.periodic_tick_interval_s))
        while not self._stop_event.wait(sleep_s):
            try:
                run_periodic_loops(
                    ml=self._ml,
                    reconcile=self._reconcile,
                    payment_jobs=self._payment_jobs,
                    offer_outcome=self._offer_outcome,
                    loop_health=self._loop_health,
                    last_loop_err_ms=self._last_loop_err_ms,
                    event_log=self._event_log,
                )
            except Exception as exc:
                logger.exception('telegram webhook periodic loop failure', exc_info=exc)


__all__ = ['TelegramWebhookConfig', 'TelegramWebhookRuntime']
