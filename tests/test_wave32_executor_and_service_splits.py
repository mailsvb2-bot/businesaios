from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_executor_split_uses_single_context_support() -> None:
    src = _read("runtime/executor.py")
    assert "runtime.executor_runtime_support" in src
    context_src = _read("runtime/execution/context.py")
    assert "def assert_called_from_executor" in context_src


def test_strategic_finance_service_split_present() -> None:
    src = _read("core/finance/strategic/services/strategic_finance_service.py")
    assert "strategic_finance_service_support" in src
    assert "build_artifacts(" in src


def test_experiments_service_split_present() -> None:
    src = _read("core/experiments/service.py")
    assert "service_support" in src
    assert "build_evaluation_summary" in src


def test_meta_connector_split_present() -> None:
    src = _read("interfaces/ads/meta_connector.py")
    assert "meta_connector_support" in src
    assert "load_meta_campaigns" in src


def test_outbound_queue_split_present() -> None:
    src = _read("interfaces/telegram/outbound/outbound_queue.py")
    assert "outbound_queue_support" in src
    assert "build_queue_metrics_snapshot" in src
