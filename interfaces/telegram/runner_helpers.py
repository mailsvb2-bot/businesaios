from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from core.observability.silent import swallow
from runtime.boot.env import env_float, env_int

logger = logging.getLogger(__name__)


def env_ms(name: str, default_s: float, lo: int, hi: int) -> int:
    ms = int(env_float(name, float(default_s)) * 1000)
    return max(lo, min(hi, ms))


def env_hours(name: str, default_h: int, lo: int, hi: int) -> int:
    value = env_int(name, int(default_h), lo=lo, hi=hi)
    return max(lo, min(hi, value))


def run_loop_tick(*, name: str, fn: Callable[[], None], loop_health: dict[str, dict[str, Any]], last_loop_err_ms: dict[str, int], event_log: Any) -> None:
    try:
        now_ms = int(time.time() * 1000)
        try:
            if name in loop_health:
                loop_health[name]["last_tick_ms"] = now_ms
        except Exception:
            swallow(__name__, "interfaces/telegram/runner_helpers.py")
        fn()
        try:
            if name in loop_health:
                loop_health[name]["last_ok_ms"] = now_ms
        except Exception:
            swallow(__name__, "interfaces/telegram/runner_helpers.py")
    except Exception as exc:
        now_ms = int(time.time() * 1000)
        try:
            if name in loop_health:
                loop_health[name]["last_err_ms"] = now_ms
                loop_health[name]["last_err"] = type(exc).__name__
        except Exception:
            swallow(__name__, "interfaces/telegram/runner_helpers.py")
        prev = int(last_loop_err_ms.get(name, 0))
        if (now_ms - prev) >= 30_000:
            last_loop_err_ms[name] = now_ms
            try:
                logger.exception("telegram loop error in %s: %r", name, exc)
            except Exception:
                swallow(__name__, "interfaces/telegram/runner_helpers.py")
            try:
                if event_log is not None and hasattr(event_log, "emit_error"):
                    event_log.emit_error(
                        event_type=f"telegram_loop_error:{name}",
                        source="telegram.runner",
                        user_id="system",
                        details={"error": type(exc).__name__},
                    )
            except Exception:
                swallow(__name__, "interfaces/telegram/runner_helpers.py")
