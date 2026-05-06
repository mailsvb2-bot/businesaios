from __future__ import annotations


FORBIDDEN_DECISION_GATEWAY_METHODS: tuple[str, ...] = (
    "decide",
    "select_winner",
    "choose_winner",
    "execute_action",
    "filter_candidates",
    "narrow_action_space",
)


def assert_decision_gateway_api(method_names: tuple[str, ...]) -> None:
    forbidden = set(FORBIDDEN_DECISION_GATEWAY_METHODS).intersection(method_names)
    if forbidden:
        joined = ", ".join(sorted(forbidden))
        raise RuntimeError(
            "decision gateway must remain a single-path bridge only; "
            f"forbidden methods detected: {joined}"
        )
