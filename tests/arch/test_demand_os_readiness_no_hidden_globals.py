from __future__ import annotations

from pathlib import Path


def test_demand_os_readiness_does_not_mutate_builtins() -> None:
    text = Path("demand_os/demand_os_readiness.py").read_text(encoding="utf-8")
    assert "builtins." not in text
    assert "_CompatDecisionService" not in text


def test_demand_os_readiness_allows_only_canonical_decision_methods() -> None:
    text = Path("demand_os/demand_os_readiness.py").read_text(encoding="utf-8")
    assert "('issue', 'decide')" in text
    assert "route" not in text.split("_DECISION_CORE_METHOD_ALTERNATIVES", 1)[1].split("\n", 2)[0]
