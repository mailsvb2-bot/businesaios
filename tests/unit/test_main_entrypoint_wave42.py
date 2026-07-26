from __future__ import annotations

import runpy
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

import main as sut


class Env:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def str(self, name, default=""):
        return self.values.get(name, default)

    def bool(self, name, default=False):
        return bool(self.values.get(name, default))


def install_main_dependencies(monkeypatch, *, env=None, logging_error=None, normalized="dev"):
    env = env or Env()
    configured = Mock()
    if logging_error is not None:
        configured.side_effect = logging_error
    throttled = Mock()
    mode_gate = SimpleNamespace(
        validate_run_mode=Mock(),
        startup_summary=Mock(return_value="ready"),
    )
    tenant_check = SimpleNamespace(tenant_self_check=Mock())
    canonical_env = SimpleNamespace(normalize_env=Mock(return_value=normalized))

    monkeypatch.setattr(sut, "env_guard_production_mode", Mock())
    monkeypatch.setattr(sut, "env_str", env.str)
    monkeypatch.setattr(sut, "env_bool", env.bool)
    monkeypatch.setattr(sut, "_observability", lambda: (configured, throttled))
    monkeypatch.setattr(sut, "_mode_gate", lambda: mode_gate)
    monkeypatch.setattr(sut, "_tenant_self_check", lambda: tenant_check)
    monkeypatch.setattr(sut, "_canonical_env", lambda: canonical_env)
    return SimpleNamespace(
        configured=configured,
        throttled=throttled,
        mode_gate=mode_gate,
        tenant_check=tenant_check,
        canonical_env=canonical_env,
    )


def test_lazy_import_boundaries_and_compatibility_exports(monkeypatch):
    imported = []

    def fake_import(name):
        imported.append(name)
        module = SimpleNamespace()
        if name == "runtime.entrypoints.telegram_longpoll":
            module.build_system = Mock(return_value="built")
            module.runtime_bootstrap = Mock()
        elif name == "core.observability.structured_logging":
            module.configure_structured_logging = "configure"
        elif name == "core.observability.throttled_logger":
            module.exception_throttled = "throttled"
        return module

    monkeypatch.setattr(sut, "import_module", fake_import)

    assert sut._telegram_ep() is not None
    assert sut._canonical_env() is not None
    assert sut._tenant() is not None
    assert sut._mode_gate() is not None
    assert sut._tenant_self_check() is not None
    assert sut._sovereign_bootstrap() is not None
    assert sut._observability() == ("configure", "throttled")
    assert sut.build_system(1, mode="safe") == "built"
    sut._bootstrap_runtime_process()

    assert imported == [
        "runtime.entrypoints.telegram_longpoll",
        "runtime.boot.canonical.env",
        "runtime.boot.canonical.tenant",
        "runtime.boot.mode_gate",
        "runtime.boot.tenant_self_check",
        "runtime.bootstrap",
        "core.observability.structured_logging",
        "core.observability.throttled_logger",
        "runtime.entrypoints.telegram_longpoll",
        "runtime.entrypoints.telegram_longpoll",
    ]


def test_env_wrappers_and_tenant_resolution(monkeypatch):
    values = {"A": "value", "TENANT_ID": " fallback "}
    monkeypatch.setattr(
        sut, "env_str", lambda name, default="": values.get(name, default)
    )
    monkeypatch.setattr(sut, "env_bool", lambda name, default=False: name == "YES")

    assert sut._env_str("A") == "value"
    assert sut._env_bool("YES") is True

    monkeypatch.setattr(
        sut,
        "_tenant",
        lambda: SimpleNamespace(resolve_tenant=lambda event_log: "tenant-from-log"),
    )
    assert sut._resolve_runtime_tenant_id(object()) == "tenant-from-log"

    monkeypatch.setattr(
        sut,
        "_tenant",
        lambda: SimpleNamespace(resolve_tenant=lambda event_log: ""),
    )
    assert sut._resolve_runtime_tenant_id(object()) == "fallback"


def test_run_demo_success_prints_events_and_uses_defaults(monkeypatch):
    env = Env({"PRINT_EVENTS": True})
    monkeypatch.setattr(sut, "_env_str", env.str)
    monkeypatch.setattr(sut, "_env_bool", env.bool)
    monkeypatch.setattr(sut.time, "time", lambda: 123.456)
    world_state = Mock(return_value="state")
    monkeypatch.setattr(
        sut,
        "_telegram_ep",
        lambda: SimpleNamespace(WorldStateV1=world_state),
    )
    core = SimpleNamespace(optimize=Mock(return_value="envelope"))
    result = SimpleNamespace(ok=True, decision_id="decision-1")
    executor = SimpleNamespace(execute=Mock(return_value=result))
    events = ["one", "two"]

    sut._run_demo(core, executor, events)

    world_state.assert_called_once_with(
        schema_version=1,
        user={"timezone": "Europe/Amsterdam"},
        session={"text": "/start", "command": "/start", "args": ""},
        product={"name": "DemoProduct"},
        economy={},
        timestamp_ms=123456,
        user_id="demo_user",
        meta={},
    )
    core.optimize.assert_called_once_with("state")
    executor.execute.assert_called_once_with("envelope")


def test_run_demo_failure_and_no_event_projection(monkeypatch):
    monkeypatch.setattr(sut, "_env_str", lambda name, default="": default)
    monkeypatch.setattr(sut, "_env_bool", lambda name, default=False: False)
    monkeypatch.setattr(
        sut,
        "_telegram_ep",
        lambda: SimpleNamespace(WorldStateV1=lambda **kwargs: kwargs),
    )
    result = SimpleNamespace(ok=False, error="blocked")

    with pytest.raises(RuntimeError, match="demo e2e smoke failed: blocked"):
        sut._run_demo(
            SimpleNamespace(optimize=lambda state: state),
            SimpleNamespace(execute=lambda envelope: result),
            [],
        )


def test_run_demo_e2e_smoke_requires_decision_execution(monkeypatch):
    bootstrap_process = Mock()
    monkeypatch.setattr(sut, "_bootstrap_runtime_process", bootstrap_process)
    monkeypatch.setattr(
        sut,
        "_sovereign_bootstrap",
        lambda: SimpleNamespace(
            bootstrap_runtime=lambda: SimpleNamespace(
                artifacts=SimpleNamespace(exports=None)
            )
        ),
    )

    with pytest.raises(RuntimeError, match="decision_execution export missing"):
        sut._run_demo_e2e_smoke()
    bootstrap_process.assert_called_once_with()


def test_run_demo_e2e_smoke_calls_optional_audit_and_accepts_missing_callback(
    monkeypatch,
):
    monkeypatch.setattr(sut, "_bootstrap_runtime_process", Mock())
    audit = Mock()

    def runtime(audit_events):
        return SimpleNamespace(
            artifacts=SimpleNamespace(
                exports=SimpleNamespace(
                    decision_execution=object(),
                    observability=SimpleNamespace(audit_events=audit_events),
                )
            ),
            state=SimpleNamespace(ready=True),
            services=(1, 2),
        )

    monkeypatch.setattr(
        sut,
        "_sovereign_bootstrap",
        lambda: SimpleNamespace(bootstrap_runtime=lambda: runtime(audit)),
    )
    sut._run_demo_e2e_smoke()
    audit.assert_called_once_with()

    monkeypatch.setattr(
        sut,
        "_sovereign_bootstrap",
        lambda: SimpleNamespace(bootstrap_runtime=lambda: runtime(None)),
    )
    sut._run_demo_e2e_smoke()


def test_main_demo_bounded_path(monkeypatch):
    deps = install_main_dependencies(monkeypatch, env=Env({"RUN_MODE": " Demo "}))
    e2e = Mock()
    monkeypatch.setattr(sut, "_run_demo_e2e_smoke", e2e)

    sut.main()

    deps.configured.assert_called_once_with(enabled=False, level="INFO")
    deps.mode_gate.validate_run_mode.assert_called_once_with("demo")
    deps.tenant_check.tenant_self_check.assert_called_once_with()
    e2e.assert_not_called()


def test_main_demo_e2e_path(monkeypatch):
    install_main_dependencies(
        monkeypatch,
        env=Env({"MODE": "demo", "DEMO_E2E_SMOKE": True}),
    )
    e2e = Mock()
    monkeypatch.setattr(sut, "_run_demo_e2e_smoke", e2e)

    sut.main()

    e2e.assert_called_once_with()


def test_main_evolution_mode(monkeypatch):
    install_main_dependencies(monkeypatch, env=Env({"RUN_MODE": "evolution"}))
    evolution = ModuleType("runtime.evolution.main")
    evolution.main = Mock()
    monkeypatch.setitem(sys.modules, "runtime.evolution.main", evolution)

    sut.main()

    evolution.main.assert_called_once_with()


def test_main_logging_failure_is_throttled_in_dev(monkeypatch):
    deps = install_main_dependencies(
        monkeypatch,
        env=Env({"RUN_MODE": "demo"}),
        logging_error=ValueError("bad logging"),
        normalized="dev",
    )

    sut.main()

    deps.throttled.assert_called_once()
    deps.canonical_env.normalize_env.assert_called_once_with("dev")


def test_main_logging_failure_is_fatal_in_production(monkeypatch):
    deps = install_main_dependencies(
        monkeypatch,
        env=Env({"APP_ENV": "prod", "RUN_MODE": "demo"}),
        logging_error=RuntimeError("bad logging"),
        normalized="prod",
    )

    with pytest.raises(RuntimeError, match="bad logging"):
        sut.main()
    deps.throttled.assert_called_once()


def telegram_ep(*, event_log=None):
    event_log = [] if event_log is None else event_log
    return SimpleNamespace(
        runtime_bootstrap=Mock(),
        build_system=Mock(
            return_value=(
                "core",
                "executor",
                event_log,
                "event-store",
                "payment-outbox",
                "stack",
                "learning-job",
            )
        ),
        run_telegram=Mock(),
    )


def install_hard_gate(monkeypatch):
    module = ModuleType("runtime.boot.tenant_hard_gate")
    module.hard_gate = Mock()
    monkeypatch.setitem(sys.modules, "runtime.boot.tenant_hard_gate", module)
    return module.hard_gate


def test_main_telegram_happy_path(monkeypatch):
    deps = install_main_dependencies(monkeypatch, env=Env({"RUN_MODE": "telegram"}))
    ep = telegram_ep(event_log=["event"])
    monkeypatch.setattr(sut, "_telegram_ep", lambda: ep)
    monkeypatch.setattr(
        sut,
        "_tenant",
        lambda: SimpleNamespace(resolve_tenant=lambda event_log: "tenant-a"),
    )
    hard_gate = install_hard_gate(monkeypatch)

    sut.main()

    ep.runtime_bootstrap.assert_called_once_with()
    hard_gate.assert_called_once_with(
        run_mode="telegram",
        tenant_id="tenant-a",
        event_store="event-store",
        event_log=["event"],
    )
    ep.run_telegram.assert_called_once_with(
        core="core",
        executor="executor",
        event_log=["event"],
        event_store="event-store",
        payment_outbox="payment-outbox",
        stack="stack",
        learning_job="learning-job",
    )
    deps.throttled.assert_not_called()


def test_main_tenant_resolution_failure_uses_env_fallback(monkeypatch):
    deps = install_main_dependencies(
        monkeypatch,
        env=Env({"RUN_MODE": "telegram", "TENANT_ID": " tenant-fallback "}),
    )
    ep = telegram_ep()
    monkeypatch.setattr(sut, "_telegram_ep", lambda: ep)
    monkeypatch.setattr(
        sut,
        "_resolve_runtime_tenant_id",
        Mock(side_effect=ValueError("bad event log")),
    )
    hard_gate = install_hard_gate(monkeypatch)

    sut.main()

    assert hard_gate.call_args.kwargs["tenant_id"] == "tenant-fallback"
    assert deps.throttled.call_count == 1


def test_main_missing_tenant_warns_in_dev_and_continues(monkeypatch):
    deps = install_main_dependencies(
        monkeypatch,
        env=Env({"RUN_MODE": "telegram"}),
        normalized="dev",
    )
    ep = telegram_ep()
    monkeypatch.setattr(sut, "_telegram_ep", lambda: ep)
    monkeypatch.setattr(sut, "_resolve_runtime_tenant_id", lambda event_log: "")
    hard_gate = install_hard_gate(monkeypatch)

    sut.main()

    assert deps.throttled.call_count == 1
    deps.canonical_env.normalize_env.assert_called_once_with("dev")
    assert hard_gate.call_args.kwargs["tenant_id"] == ""


def test_main_missing_tenant_fails_closed_in_production(monkeypatch):
    deps = install_main_dependencies(
        monkeypatch,
        env=Env({"APP_ENV": "prod", "RUN_MODE": "telegram"}),
        normalized="prod",
    )
    ep = telegram_ep()
    monkeypatch.setattr(sut, "_telegram_ep", lambda: ep)
    monkeypatch.setattr(sut, "_resolve_runtime_tenant_id", lambda event_log: "")
    install_hard_gate(monkeypatch)

    with pytest.raises(RuntimeError, match="tenant_id required"):
        sut.main()
    assert deps.throttled.call_count == 1


def test_module_script_guard_executes_main(monkeypatch):
    env_module = sys.modules["runtime.boot.env"]
    monkeypatch.setattr(env_module, "env_guard_production_mode", Mock())
    monkeypatch.setattr(
        env_module,
        "env_str",
        lambda name, default="": {"RUN_MODE": "demo"}.get(name, default),
    )
    monkeypatch.setattr(
        env_module,
        "env_bool",
        lambda name, default=False: default,
    )

    structured = ModuleType("core.observability.structured_logging")
    structured.configure_structured_logging = Mock()
    throttled = ModuleType("core.observability.throttled_logger")
    throttled.exception_throttled = Mock()
    mode_gate = ModuleType("runtime.boot.mode_gate")
    mode_gate.validate_run_mode = Mock()
    mode_gate.startup_summary = Mock(return_value="ready")
    tenant_check = ModuleType("runtime.boot.tenant_self_check")
    tenant_check.tenant_self_check = Mock()
    monkeypatch.setitem(sys.modules, structured.__name__, structured)
    monkeypatch.setitem(sys.modules, throttled.__name__, throttled)
    monkeypatch.setitem(sys.modules, mode_gate.__name__, mode_gate)
    monkeypatch.setitem(sys.modules, tenant_check.__name__, tenant_check)

    runpy.run_path(str(Path(sut.__file__)), run_name="__main__")

    env_module.env_guard_production_mode.assert_called_once_with()
    mode_gate.validate_run_mode.assert_called_once_with("demo")


def test_run_demo_print_events_empty_iterable_covers_loop_exit(monkeypatch):
    monkeypatch.setattr(sut, "_env_str", lambda name, default="": default)
    monkeypatch.setattr(
        sut,
        "_env_bool",
        lambda name, default=False: name == "PRINT_EVENTS",
    )
    monkeypatch.setattr(
        sut,
        "_telegram_ep",
        lambda: SimpleNamespace(WorldStateV1=lambda **kwargs: kwargs),
    )
    sut._run_demo(
        SimpleNamespace(optimize=lambda state: state),
        SimpleNamespace(execute=lambda envelope: SimpleNamespace(ok=True)),
        [],
    )


def test_run_demo_success_without_event_projection(monkeypatch):
    monkeypatch.setattr(sut, "_env_str", lambda name, default="": default)
    monkeypatch.setattr(sut, "_env_bool", lambda name, default=False: False)
    monkeypatch.setattr(
        sut,
        "_telegram_ep",
        lambda: SimpleNamespace(WorldStateV1=lambda **kwargs: kwargs),
    )
    sut._run_demo(
        SimpleNamespace(optimize=lambda state: state),
        SimpleNamespace(execute=lambda envelope: SimpleNamespace(ok=True)),
        ["not-projected"],
    )
