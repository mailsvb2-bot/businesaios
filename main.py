from __future__ import annotations

"""Sovereign process entrypoint.

Hard invariants:
- .optimize(...) calls are allowed ONLY here.
- Bootstrap must be explicit (no side-effects on import).

Config: all env vars are documented in .env.example. Canonical loader: runtime.platform.config.registry.CONFIG.
"""

import logging
import time
from importlib import import_module
from typing import Any

CANON_MAIN_RUNTIME_ENTRYPOINT = True
CANON_MAIN_USES_RUNTIME_ENTRYPOINT_SHIM = True
CANON_MAIN_NO_LEGACY_BOOT_IMPORTS = True
CANON_MAIN_IMPORT_LIGHTWEIGHT = True
CANON_MAIN_DEMO_BOUNDED_SMOKE = True
CANON_MAIN_DEMO_E2E_SMOKE_OPT_IN = True


def _telegram_ep() -> Any:
    return import_module("runtime.entrypoints.telegram_longpoll")


def _env() -> Any:
    return import_module("runtime.boot.env")


def _canonical_env() -> Any:
    return import_module("runtime.boot.canonical.env")


def _tenant() -> Any:
    return import_module("runtime.boot.canonical.tenant")


def _mode_gate() -> Any:
    return import_module("runtime.boot.mode_gate")


def _tenant_self_check() -> Any:
    return import_module("runtime.boot.tenant_self_check")


def _observability() -> tuple[Any, Any]:
    structured_logging = import_module("core.observability.structured_logging")
    throttled_logger = import_module("core.observability.throttled_logger")
    return structured_logging.configure_structured_logging, throttled_logger.exception_throttled


# Backward-compatible export for tests/tools. Resolved lazily to avoid heavy boot imports.
def build_system(*args: Any, **kwargs: Any) -> Any:
    return _telegram_ep().build_system(*args, **kwargs)


log = logging.getLogger("businesaios.main")


def _env_str(name: str, default: str = "") -> str:
    return _env().env_str(name, default)


def _env_bool(name: str, default: bool = False) -> bool:
    return _env().env_bool(name, default)


def _resolve_runtime_tenant_id(event_log: Any) -> str:
    return _tenant().resolve_tenant(event_log) or _env_str("TENANT_ID", "").strip()


def _bootstrap_runtime_process() -> None:
    _telegram_ep().runtime_bootstrap()


def _run_demo(core: Any, executor: Any, event_log: Any) -> None:
    ep = _telegram_ep()
    state = ep.WorldStateV1(
        schema_version=1,
        user={"timezone": _env_str("SYSTEM_TZ", "Europe/Amsterdam")},
        session={"text": "/start", "command": "/start", "args": ""},
        product={"name": "DemoProduct"},
        economy={},
        timestamp_ms=int(time.time() * 1000),
        user_id=_env_str("DEMO_USER_ID", "demo_user"),
        meta={},
    )
    env = core.optimize(state)
    res = executor.execute(env)
    log.info("Demo e2e smoke executed=%s decision_id=%s", bool(res.ok), getattr(res, "decision_id", ""))
    if not bool(getattr(res, "ok", False)):
        raise RuntimeError(f"demo e2e smoke failed: {getattr(res, 'error', None)}")

    if _env_bool("PRINT_EVENTS", False):
        for e in list(event_log):
            log.info("event=%s", e)


def _run_demo_e2e_smoke() -> None:
    """Run the bounded local decision -> execution smoke path.

    The default demo path intentionally stays lightweight. Operators can set
    DEMO_E2E_SMOKE=1 to prove the canonical DecisionCore/RuntimeExecutor path
    without starting Telegram polling/webhook transport.
    """
    _bootstrap_runtime_process()
    core, executor, event_log, _event_store, _payment_outbox, stack, _learning_job = _telegram_ep().build_system()
    try:
        _run_demo(core=core, executor=executor, event_log=event_log)
    finally:
        try:
            stack.close()
        except Exception:
            log.exception("Demo e2e smoke stack close failed")


def main() -> None:
    env = _env()
    env.env_guard_production_mode()

    configure_structured_logging, exception_throttled = _observability()
    try:
        configure_structured_logging(enabled=env.env_bool("STRUCTURED_LOGS", False), level=env.env_str("LOG_LEVEL", "INFO"))
    except (ImportError, AttributeError, TypeError, ValueError, KeyError, OSError, RuntimeError) as e:
        exception_throttled(log, key="main.configure_structured_logging", msg=f"main: configure_structured_logging failed: {e}")
        normalize_env = _canonical_env().normalize_env
        if normalize_env(env.env_str("APP_ENV", env.env_str("ENV", "dev"))) == "prod":
            raise

    run_mode = (env.env_str("RUN_MODE", "") or env.env_str("MODE", "demo") or "demo").strip().lower()

    mode_gate = _mode_gate()
    mode_gate.validate_run_mode(run_mode)
    _tenant_self_check().tenant_self_check()
    log.info("startup=%s", mode_gate.startup_summary(run_mode))

    if run_mode == "evolution":
        from runtime.evolution.main import main as evolution_main

        evolution_main()
        return

    if run_mode == "demo":
        if _env_bool("DEMO_E2E_SMOKE", False):
            _run_demo_e2e_smoke()
            return
        # Bounded startup smoke: demo must prove the process can boot without
        # importing or starting the heavy Telegram/runtime graph. To prove the
        # full decision -> execution path, set DEMO_E2E_SMOKE=1.
        log.info("Demo startup smoke passed")
        return

    ep = _telegram_ep()
    _bootstrap_runtime_process()
    core, executor, event_log, event_store, payment_outbox, stack, learning_job = ep.build_system()

    try:
        tenant_id = _resolve_runtime_tenant_id(event_log)
    except (AttributeError, TypeError, ValueError) as e:
        exception_throttled(log, key="main.tenant_id", msg=f"event_log wiring failed: {e}")
        tenant_id = env.env_str("TENANT_ID", "").strip()
    if not tenant_id:
        exception_throttled(log, key="main.tenant_id", msg="boot failure: tenant_id missing (event_log has no tenant_id and TENANT_ID env unset)")
        normalize_env = _canonical_env().normalize_env
        if normalize_env(env.env_str("APP_ENV", env.env_str("ENV", "dev"))) == "prod":
            raise RuntimeError("boot failure: tenant_id required")

    from runtime.boot.tenant_hard_gate import hard_gate

    hard_gate(run_mode=run_mode, tenant_id=tenant_id, event_store=event_store, event_log=event_log)

    ep.run_telegram(
        core=core,
        executor=executor,
        event_log=event_log,
        event_store=event_store,
        payment_outbox=payment_outbox,
        stack=stack,
        learning_job=learning_job,
    )


if __name__ == '__main__':
    main()
