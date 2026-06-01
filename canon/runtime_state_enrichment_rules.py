from __future__ import annotations

FORBIDDEN_RUNTIME_ENRICHMENT_KEYS: tuple[str, ...] = (
    "winner",
    "winning_candidate",
    "candidate_ids",
    "allowed_candidates",
    "filtered_candidates",
    "action_space",
    "direct_action",
    "final_decision",
)


def assert_runtime_enrichment_payload(payload: dict[str, object]) -> None:
    forbidden = set(FORBIDDEN_RUNTIME_ENRICHMENT_KEYS).intersection(payload.keys())
    if forbidden:
        joined = ", ".join(sorted(forbidden))
        raise RuntimeError(
            "runtime enrichment payload contains forbidden routing/action fields; "
            f"detected: {joined}"
        )
