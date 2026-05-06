from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_behavior_graph_split_files_removed() -> None:
    assert not (ROOT / "runtime/platform/behavior_graph/sqlite_behavior_graph_store_part1.py").exists()
    assert not (ROOT / "runtime/platform/behavior_graph/sqlite_behavior_graph_store_part2.py").exists()


def test_event_store_split_files_removed_but_contract_shim_remains_explicit() -> None:
    assert not (ROOT / "runtime/platform/event_store/postgres_event_store_part1.py").exists()
    assert not (ROOT / "runtime/platform/event_store/postgres_event_store_part2.py").exists()
    assert not (ROOT / "runtime/platform/event_store/sqlite_read_queries_part1.py").exists()
    assert not (ROOT / "runtime/platform/event_store/sqlite_read_queries_part2.py").exists()
    text = (ROOT / "runtime/platform/event_store/contract.py").read_text(encoding="utf-8")
    assert "CANON_TRANSITION_SURFACE = True" in text or "EventAppendProtocol" in text


def test_runtime_serving_validator_shim_stays_thin_if_present() -> None:
    path = ROOT / "runtime/platform/support/serving/runtime/action_validator.py"
    text = path.read_text(encoding="utf-8")
    assert "CANON_COMPAT_SHIM = True" in text
    assert "application.decision.action_validator" in text


def test_historical_event_store_compat_module_removed() -> None:
    assert not (ROOT / "runtime/platform/event_store/_historical_split_compat.py").exists()
