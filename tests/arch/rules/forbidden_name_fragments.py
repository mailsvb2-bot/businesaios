from __future__ import annotations

FORBIDDEN_DECISION_FRAGMENTS: tuple[str, ...] = (
    "choose_winner",
    "select_winner",
    "auto_select",
    "execute_action",
    "commit_final_decision",
    "fast_track_decision",
    "route_direct_action",
    "narrow_action_space",
    "filter_action_space",
)

FORBIDDEN_ROUTING_FRAGMENTS_OUTSIDE_GATEWAY: tuple[str, ...] = (
    "route_",
    "dispatch_",
    "forward_",
)

FORBIDDEN_PACKET_CONTROL_KEYS: tuple[str, ...] = (
    "winner",
    "winning_candidate",
    "final_decision",
    "candidate_ids",
    "allowed_candidates",
    "filtered_candidates",
    "executor_command",
    "action_space",
)
