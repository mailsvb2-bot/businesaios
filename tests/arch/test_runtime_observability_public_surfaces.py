from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_runtime_observability_public_api_exists() -> None:
    text = _read("runtime/observability/__init__.py")
    assert "CANON_RUNTIME_OBSERVABILITY_PUBLIC_API = True" in text
    assert "CANON_RUNTIME_OBSERVABILITY_PUBLIC_API = True" in text
    assert ("from core.observability.structured_logging import (" in text) or ("build_package_alias_namespace" in text)
    assert ("from core.observability.perf import (" in text) or ("build_package_alias_namespace" in text)


def test_runtime_perf_public_api_exists() -> None:
    text = _read("runtime/observability/perf.py")
    assert "CANON_RUNTIME_PERF_PUBLIC_API = True" in text
    assert "from runtime.observability import (" in text or "runtime.observability" in text
    assert "core.observability.perf" not in text


def test_runtime_no_longer_imports_core_structured_logging_directly() -> None:
    direct_paths = [
        "runtime/boot/boot_observability.py",
        "runtime/boot/phase_outbound.py",
        "runtime/execution/executor_entrypoint.py",
        "runtime/execution/executor_recovery_entrypoint.py",
        "runtime/execution/world_model_pin_runtime.py",
    ]
    for rel in direct_paths:
        text = _read(rel)
        assert "core.observability.structured_logging" not in text, rel
        assert "runtime.observability" in text, rel


def test_runtime_no_longer_imports_core_perf_directly() -> None:
    direct_paths = [
        "runtime/executor_recovery_flow.py",
        "runtime/observability/sla_auto_accelerator.py",
        "runtime/observability/tracing.py",
        "runtime/boot/phase_outbound.py",
    ]
    for rel in direct_paths:
        text = _read(rel)
        assert "core.observability.perf" not in text, rel
        assert "runtime.observability.perf" in text, rel
