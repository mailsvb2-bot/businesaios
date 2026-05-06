from __future__ import annotations


FORBIDDEN_ACTION_BOUNDARY_KEYS: tuple[str, ...] = (
    "action_space",
    "candidate_ids",
    "allowed_candidates",
    "filtered_candidates",
    "winning_candidate",
    "winner",
    "executor_command",
    "final_decision",
)


def assert_action_boundary_clean(payload: dict[str, object]) -> None:
    forbidden = set(FORBIDDEN_ACTION_BOUNDARY_KEYS).intersection(payload.keys())
    if forbidden:
        joined = ", ".join(sorted(forbidden))
        raise RuntimeError(
            "payload crosses action boundary with forbidden decision-space fields; "
            f"detected: {joined}"
        )
