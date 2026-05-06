from __future__ import annotations

from pathlib import Path


def test_arch_sensitive_support_files_remain_real_files() -> None:
    files = [
        "runtime/platform/support/observability/logging.py",
        "runtime/platform/support/events/event_bus.py",
        "runtime/platform/support/contracts/promotion_contract.py",
        "runtime/platform/support/optimization/promotion_decision.py",
    ]
    for rel in files:
        text = Path(rel).read_text(encoding="utf-8")
        assert text.strip()
