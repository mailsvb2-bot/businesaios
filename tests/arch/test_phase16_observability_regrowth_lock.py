from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")

def test_observability_role_docs_and_public_surfaces_remain() -> None:
    role_docs = [
        "observability/CANON_NAMESPACE_ROLE.md",
        "core/observability/CANON_NAMESPACE_ROLE.md",
        "runtime/observability/CANON_NAMESPACE_ROLE.md",
        "observability/platform/observability/CANON_NAMESPACE_ROLE.md",
        "infrastructure/observability/CANON_NAMESPACE_ROLE.md",
        "observability/platform/telemetry/CANON_NAMESPACE_ROLE.md",
    ]
    for rel in role_docs:
        assert (ROOT / rel).exists(), rel
        assert (ROOT / rel).read_text(encoding="utf-8").strip(), rel

    runtime_public = _read("runtime/observability/__init__.py")
    assert "CANON_RUNTIME_OBSERVABILITY_PUBLIC_API = True" in runtime_public
    assert "structured_logging" in runtime_public
    assert "perf" in runtime_public

    runtime_perf = _read("runtime/observability/perf.py")
    assert "CANON_RUNTIME_PERF_PUBLIC_API = True" in runtime_perf
    assert "runtime.observability" in runtime_perf

def test_observability_owner_boundaries_stay_explicit() -> None:
    platform_init = _read("observability/platform/__init__.py")
    assert "__getattr__" in platform_init
    assert "install_public_api_alias(__name__)" in platform_init

    event_bus = _read("observability/event_bus.py")
    assert "AppendOnlyTopicLog" in event_bus
    assert "TopicSubscriberRegistry" in event_bus

    runtime_event_bus = _read("runtime/platform/support/events/__init__.py")
    assert "AppendOnlyTopicLog" in runtime_event_bus

    runtime_support_observability = _read("runtime/platform/support/observability/__init__.py")
    assert "CANON_COMPAT_SHIM = True" in runtime_support_observability
    assert '"metrics": "runtime.observability.metrics"' in runtime_support_observability

    runtime_support_explainability = _read("runtime/platform/support/explainability/__init__.py")
    assert "CANON_COMPAT_SHIM = True" in runtime_support_explainability
    assert '"decision_trace": "core.decision.runtime_decision_trace"' in runtime_support_explainability

def test_runtime_boot_and_observability_wiring_stay_complete() -> None:
    boot_public = _read("boot/__init__.py")
    assert "CANON_BOOT_PUBLIC_API_COMPAT_SHELL = True" in boot_public
    assert "install_public_api_alias(__name__)" in boot_public
    assert "def __getattr__(name: str) -> Any:" in boot_public

    sla = _read("runtime/observability/sla_auto_accelerator.py")
    assert "os.getenv(" not in sla
    assert "env_int(" in sla

    runtime_exec_init = _read("runtime/execution/__init__.py")
    assert '"telemetry": "runtime.observability.telemetry"' in runtime_exec_init
