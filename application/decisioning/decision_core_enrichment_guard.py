from __future__ import annotations

FORBIDDEN_ENRICHMENT_KEYS: tuple[str, ...] = (
    "final_decision",
    "winner",
    "winning_candidate",
    "candidate_ids",
    "allowed_candidates",
    "filtered_candidates",
    "executor_command",
)


def assert_safe_decision_core_enrichment(payload: dict[str, object]) -> None:
    forbidden = set(FORBIDDEN_ENRICHMENT_KEYS).intersection(payload.keys())
    if forbidden:
        joined = ", ".join(sorted(forbidden))
        raise RuntimeError(
            "decision core enrichment attempts to carry forbidden decision/narrowing keys; "
            f"detected: {joined}"
        )
