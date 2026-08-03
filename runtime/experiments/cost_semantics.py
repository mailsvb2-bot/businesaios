from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


def validate_reservation_cost(value: object) -> float:
    try:
        number = float(value or 0.0)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("LIVE_CANARY_RESERVATION_COST_INVALID") from exc
    if not math.isfinite(number):
        raise RuntimeError("LIVE_CANARY_RESERVATION_COST_NON_FINITE")
    if number < 0:
        raise RuntimeError("LIVE_CANARY_RESERVATION_COST_NEGATIVE")
    return number


def _declared_cost(payload: Mapping[str, Any]) -> tuple[bool, object]:
    for name in ("cost", "actual_cost"):
        if name in payload and payload.get(name) not in (None, ""):
            return True, payload.get(name)
    return False, None


def _actual_cost(value: object, *, source: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"LIVE_CANARY_{source}_COST_INVALID") from exc
    if not math.isfinite(number):
        raise RuntimeError(f"LIVE_CANARY_{source}_COST_NON_FINITE")
    if number < 0:
        raise RuntimeError(f"LIVE_CANARY_{source}_COST_NEGATIVE")
    return number


def resolve_execution_cost(
    *,
    result_output: Mapping[str, Any],
    proof_payload: Mapping[str, Any],
    expected_cost: object = 0.0,
) -> float:
    reservation = validate_reservation_cost(expected_cost)
    proof_present, proof_value = _declared_cost(proof_payload)
    output_present, output_value = _declared_cost(result_output)
    proof_cost = (
        _actual_cost(proof_value, source="PROOF") if proof_present else None
    )
    output_cost = (
        _actual_cost(output_value, source="RESULT") if output_present else None
    )
    if proof_cost is not None and output_cost is not None:
        if not math.isclose(proof_cost, output_cost, rel_tol=1e-9, abs_tol=1e-9):
            raise RuntimeError("LIVE_CANARY_EXECUTION_COST_MISMATCH")
        return proof_cost
    if proof_cost is not None:
        return proof_cost
    if output_cost is not None:
        return output_cost
    if reservation > 0:
        raise RuntimeError("LIVE_CANARY_EXECUTION_COST_EVIDENCE_REQUIRED")
    return 0.0


__all__ = ["resolve_execution_cost", "validate_reservation_cost"]
