from __future__ import annotations

FORBIDDEN_WORLD_STATE_KEYS: tuple[str, ...] = (
    "final_decision",
    "winner",
    "winning_creative",
    "executor_command",
    "direct_action",
)


def assert_world_state_boundary(payload: dict[str, object]) -> None:
    forbidden = set(FORBIDDEN_WORLD_STATE_KEYS).intersection(payload.keys())
    if forbidden:
        joined = ", ".join(sorted(forbidden))
        raise RuntimeError(
            "world-state payload must not carry direct decision/execution fields; "
            f"forbidden keys detected: {joined}"
        )
