from __future__ import annotations

from uuid import uuid4


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def new_experiment_id() -> str:
    return _new_id("exp")


def new_assignment_id() -> str:
    return _new_id("asg")


def new_result_id() -> str:
    return _new_id("res")


def validate_prefixed_id(value: str, prefix: str) -> str:
    if not value or not isinstance(value, str) or not value.startswith(prefix + "_"):
        raise ValueError(f"expected id with prefix '{prefix}_', got '{value}'")
    return value
