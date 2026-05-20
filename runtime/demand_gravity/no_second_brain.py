from __future__ import annotations

from collections.abc import Mapping, Sequence


FORBIDDEN_DEMAND_METHOD_NAMES = {
    "approve",
    "bid",
    "decide",
    "execute",
    "mutate",
    "optimize_budget",
    "publish",
    "rank",
    "select_channel",
    "select_strategy",
    "spend",
}

FORBIDDEN_DEMAND_PAYLOAD_KEYS = {
    "approved",
    "autonomous_action",
    "bid_amount",
    "budget_allocation",
    "execute_now",
    "final_decision",
    "selected_strategy",
    "winner_channel",
}


class DemandGravitySecondBrainViolation(RuntimeError):
    pass


def assert_payload_has_no_decision_fields(payload: Mapping[str, object]) -> None:
    violations: list[str] = []

    def visit(value: object, path: str) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                key_text = str(key)
                next_path = f"{path}.{key_text}" if path else key_text
                if key_text in FORBIDDEN_DEMAND_PAYLOAD_KEYS:
                    violations.append(next_path)
                visit(item, next_path)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            for index, item in enumerate(value):
                visit(item, f"{path}[{index}]")

    visit(payload, "")
    if violations:
        raise DemandGravitySecondBrainViolation(
            "demand_gravity_decision_payload_forbidden:" + ",".join(sorted(violations))
        )


def assert_object_has_no_second_brain_methods(obj: object) -> None:
    names = set(dir(obj))
    violations = names & FORBIDDEN_DEMAND_METHOD_NAMES
    if violations:
        raise DemandGravitySecondBrainViolation(
            "demand_gravity_methods_forbidden:" + ",".join(sorted(violations))
        )
