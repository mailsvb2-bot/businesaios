from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_core_ai_paths_use_canonical_trace_owner() -> None:
        assert "from core.ai.decision_trace import" not in _read("core/ai/decision_runtime.py")
        assert "from core.decision.ai_decision_trace import" in _read("core/ai/decision_runtime.py")


def test_explainability_uses_canonical_trace_owner() -> None:
    text = _read("core/explainability/decision_explain.py")
    assert "from core.ai.decision_trace import" not in text
    assert "from core.decision.ai_decision_trace import DecisionTrace" in text


def test_runtime_execution_uses_runtime_observability_owner() -> None:
    for path in [
        "runtime/execution/executor_stages.py",
        "runtime/execution/executor_entrypoint.py",
        "runtime/_internal/_effects_impl.py",
        "runtime/_internal/effects_actions/telegram_actions.py",
    ]:
        text = _read(path)
        assert "from runtime.execution.telemetry import" not in text
        assert "from runtime.observability.telemetry import" in text


def test_boot_runtime_integration_uses_core_application_owner() -> None:
    text = _read("boot/runtime_integration.py")
    assert "from runtime.application.application_service import" not in text
    assert "from core.application.decision_service import DecisionApplicationService" in text



def test_runtime_telegram_transport_avoids_core_observability_compat_surface() -> None:
    text = _read("runtime/_internal/effects_actions/telegram/messaging_parts/transport.py")
    assert "from core.observability.telemetry import" not in text
    assert "from runtime.observability.telemetry import" in text
