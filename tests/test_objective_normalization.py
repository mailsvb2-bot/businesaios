from __future__ import annotations

from core.economics.objective import DEFAULT_OBJECTIVE, normalize_objective


def test_objective_normalization_aliases() -> None:
    assert normalize_objective("sales") == DEFAULT_OBJECTIVE
    assert normalize_objective("revenue") == DEFAULT_OBJECTIVE
    assert normalize_objective("conversion") == "leads"
    assert normalize_objective("clicks") == "traffic"


def test_objective_normalization_unknown_falls_back() -> None:
    assert normalize_objective("weird-objective") == DEFAULT_OBJECTIVE
    assert normalize_objective(None) == DEFAULT_OBJECTIVE
