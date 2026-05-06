from __future__ import annotations

import logging
import time
from typing import Any

from core.observability.silent import swallow
from interfaces.telegram.runner_helpers import run_loop_tick

logger = logging.getLogger(__name__)


def run_periodic_loops(*, ml: Any, reconcile: Any, payment_jobs: Any, offer_outcome: Any, loop_health: dict[str, dict[str, Any]], last_loop_err_ms: dict[str, int], event_log: Any) -> None:
    run_loop_tick(name="ml", fn=ml.tick, loop_health=loop_health, last_loop_err_ms=last_loop_err_ms, event_log=event_log)
    run_loop_tick(name="reconcile", fn=reconcile.tick, loop_health=loop_health, last_loop_err_ms=last_loop_err_ms, event_log=event_log)
    run_loop_tick(name="payment_jobs", fn=payment_jobs.tick, loop_health=loop_health, last_loop_err_ms=last_loop_err_ms, event_log=event_log)
    run_loop_tick(name="offer_outcome", fn=offer_outcome.tick, loop_health=loop_health, last_loop_err_ms=last_loop_err_ms, event_log=event_log)


def poll_updates(*, poller: Any, retry_delay: float) -> tuple[list[Any], float, int]:
    try:
        updates = poller.poll()
        return updates, 1.0, int(time.time() * 1000)
    except Exception as exc:
        next_retry = min(60.0, float(retry_delay) * 2.0)
        try:
            logger.warning("telegram poll error: %r (retry in %.1fs)", exc, next_retry)
        except Exception:
            swallow(__name__, 'interfaces/telegram/runner_loop.py')
        time.sleep(float(next_retry))
        return [], next_retry, 0


def handle_idle_poll(*, updates: list[Any], idle_sleep_s: float, last_idle_log_ms: int, last_ok_poll_ms: int, poller: Any) -> tuple[bool, int]:
    if updates:
        return False, last_idle_log_ms
    now_ms = int(time.time() * 1000)
    if (now_ms - last_idle_log_ms) >= 30_000:
        last_idle_log_ms = now_ms
        try:
            dt = 0 if last_ok_poll_ms == 0 else int((now_ms - last_ok_poll_ms) / 1000)
            logger.debug("telegram polling ok (no updates). last_ok_poll=%ss ago offset=%s", dt, poller.offset)
        except Exception:
            swallow(__name__, 'interfaces/telegram/runner_loop.py')
    time.sleep(float(idle_sleep_s))
    return True, last_idle_log_ms
