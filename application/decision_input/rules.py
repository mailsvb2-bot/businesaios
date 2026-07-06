from __future__ import annotations

from collections.abc import Mapping, Sequence
from importlib import import_module


def assert_safe_recommendations(recommendations: Sequence[object]) -> None:
    fn = import_module("canon.decision_input_rules").assert_safe_recommendations
    fn(recommendations)


def assert_safe_metadata(metadata: Mapping[str, object]) -> None:
    fn = import_module("canon.decision_input_rules").assert_safe_metadata
    fn(metadata)


__all__ = ["assert_safe_metadata", "assert_safe_recommendations"]
