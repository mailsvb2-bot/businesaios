"""Evolution entrypoint.

Runs EVOLUTION-timescale worker + optional health server.

This module MUST NOT start Telegram runtime.
"""

from __future__ import annotations


import logging
from typing import Any

from bootstrap.health_server import start_health_server
from bootstrap.mode_gate import startup_summary, validate_run_mode
from runtime.boot.tenant_self_check import tenant_self_check
from runtime.evolution.worker import build_worker_from_env, evolution_enabled
from runtime.observability.error_handling import exception_throttled
from runtime.platform.config.env_flags import env_int, env_str

log = logging.getLogger("runtime.evolution.main")


def main() -> None:
    run_mode = (env_str("RUN_MODE") or env_str("MODE") or "evolution").strip().lower()
    validate_run_mode(run_mode)
    tenant_self_check()
    if run_mode != "evolution":
        raise SystemExit(f"runtime.evolution.main must be run with RUN_MODE=evolution (got {run_mode!r})")

    log.info("startup=%s", startup_summary(run_mode))

    from runtime.boot.tenant_hard_gate import preflight_env
    preflight_env(run_mode=run_mode)

    if not evolution_enabled():
        log.warning("evolution_disabled EVOLUTION_ENABLED=0")
        return

    worker = build_worker_from_env()
    port = env_int("EVOLUTION_HEALTH_PORT", 8087, lo=0, hi=65535)

    def _state() -> dict[str, Any]:
        st = worker.state
        return {
            "ok": bool(st.ok),
            "pending": int(st.pending),
            "processed_total": int(st.processed_total),
            "processed_last_tick": int(st.processed_last_tick),
            "last_tick_ms": int(st.last_tick_ms),
            "last_ok_ms": int(st.last_ok_ms),
            "last_error": str(st.last_error or ""),
        }

    try:
        start_health_server(port=int(port), state_fn=_state, name="evolution")
    except Exception:
        exception_throttled(
            log,
            key="evolution_health_bind",
            msg="failed to start evolution health server",
        )

    worker.run_forever()


if __name__ == "__main__":
    main()
