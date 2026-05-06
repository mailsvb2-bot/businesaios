from __future__ import annotations

FORBIDDEN_RECOMMENDATION_FIELDS: tuple[str, ...] = (
    "winner",
    "winning_creative",
    "final_decision",
    "executor_command",
    "direct_action",
    "forced_action",
    "action_space",
    "filtered_candidates",
    "allowed_candidates",
    "candidate_ids",
)

FORBIDDEN_METADATA_FIELDS: tuple[str, ...] = (
    "final_decision",
    "winner",
    "executor_command",
)


def assert_safe_recommendations(recommendations: tuple[dict[str, object], ...]) -> None:
    for item in recommendations:
        forbidden = set(FORBIDDEN_RECOMMENDATION_FIELDS).intersection(item.keys())
        if forbidden:
            joined = ", ".join(sorted(forbidden))
            raise RuntimeError(
                "recommendation packet contains forbidden decision/narrowing fields; "
                f"detected: {joined}"
            )


def assert_safe_metadata(metadata: dict[str, object]) -> None:
    forbidden = set(FORBIDDEN_METADATA_FIELDS).intersection(metadata.keys())
    if forbidden:
        joined = ", ".join(sorted(forbidden))
        raise RuntimeError(
            "decision envelope metadata contains forbidden final-decision fields; "
            f"detected: {joined}"
        )
