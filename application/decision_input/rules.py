from __future__ import annotations

from importlib import import_module
from typing import Mapping, Sequence


def assert_safe_recommendations(recommendations: Sequence[object]) -> None:
    fn = getattr(import_module("canon.decision_input_rules"), "assert_safe_recommendations")
    fn(recommendations)


def assert_safe_metadata(metadata: Mapping[str, object]) -> None:
    fn = getattr(import_module("canon.decision_input_rules"), "assert_safe_metadata")
    fn(metadata)


__all__ = ["assert_safe_metadata", "assert_safe_recommendations"]
