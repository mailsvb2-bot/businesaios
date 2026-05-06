from __future__ import annotations

import importlib


def test_core_ai_decision_trace_legacy_import_resolves_to_canonical_owner() -> None:
    legacy = importlib.import_module("core.ai.decision_trace")
    canonical = importlib.import_module("core.decision.ai_decision_trace")
    assert legacy is canonical


def test_runtime_execution_telemetry_legacy_import_resolves_to_runtime_observability_owner() -> None:
    legacy = importlib.import_module("runtime.execution.telemetry")
    canonical = importlib.import_module("runtime.observability.telemetry")
    assert legacy is canonical


def test_runtime_support_metrics_legacy_import_resolves_to_runtime_observability_owner() -> None:
    legacy = importlib.import_module("runtime.platform.support.observability.metrics")
    canonical = importlib.import_module("runtime.observability.metrics")
    assert legacy is canonical


def test_runtime_support_explainability_trace_legacy_import_resolves_to_core_owner() -> None:
    legacy = importlib.import_module("runtime.platform.support.explainability.decision_trace")
    canonical = importlib.import_module("core.decision.runtime_decision_trace")
    assert legacy is canonical


def test_core_observability_telemetry_legacy_import_resolves_to_runtime_observability_owner() -> None:
    legacy = importlib.import_module("core.observability.telemetry")
    canonical = importlib.import_module("runtime.observability.telemetry")
    assert legacy is canonical
