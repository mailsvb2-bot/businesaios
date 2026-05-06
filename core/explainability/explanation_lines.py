from __future__ import annotations

from core.explainability.operator_reason import OperatorReason


def to_lines(reasons: tuple[OperatorReason, ...]) -> tuple[str, ...]:
    return tuple(item.line for item in reasons)
