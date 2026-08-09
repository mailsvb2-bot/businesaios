from __future__ import annotations

from runtime.messaging_policy.guardrails import (
    drop_blocked,
    drop_failed,
    keep_enabled,
    keep_verified_if_required,
    rotate_for_attempt_index,
    rotate_for_unanswered,
)
from runtime.messaging_policy.policy_plan import PolicyPlan
from runtime.messaging_policy.policy_request import PolicyRequest
from runtime.messaging_policy.sequence_builder import build_candidate_sequence


class MessagingPolicyResolver:
    """Deterministic delivery policy only; no ranking, persuasion, or business decisions."""

    def resolve(self, req: PolicyRequest) -> PolicyPlan:
        if req.delivery_snapshot.delivered:
            return PolicyPlan(ordered_channels=(), reason_codes=("already_delivered",), terminal_reason="already_delivered")
        if req.contact_basis == "none":
            return PolicyPlan(ordered_channels=(), reason_codes=("contact_basis_checked", "outbound_forbidden"), terminal_reason="outbound_forbidden")

        reasons: list[str] = ["contact_basis_checked"] if req.contact_basis else []
        channels = build_candidate_sequence(req)
        reasons.append("candidate_sequence_built")
        channels = keep_enabled(channels, req)
        reasons.append("enabled_filtered")
        channels = keep_verified_if_required(channels, req)
        if req.verified_only:
            reasons.append("verified_only_filtered")
        channels = drop_blocked(channels, req)
        if req.delivery_snapshot.blocked:
            reasons.append("blocked_filtered")
        channels = drop_failed(channels, req)
        if req.delivery_snapshot.failed:
            reasons.append("failed_filtered")
        channels = rotate_for_unanswered(channels, req)
        if req.unanswered_threshold_s > 0:
            reasons.append("unanswered_rotation_checked")
        channels = rotate_for_attempt_index(channels, req)
        if req.attempt_index > 0:
            reasons.append("attempt_rotation_applied")
        if not channels:
            return PolicyPlan(ordered_channels=(), reason_codes=tuple(reasons), terminal_reason="no_eligible_channel")
        return PolicyPlan(ordered_channels=channels, reason_codes=tuple(reasons), terminal_reason="")
