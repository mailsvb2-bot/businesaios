from __future__ import annotations

from execution.action_contracts import ActionSpec


def build_visual_creative_action_specs() -> dict[str, ActionSpec]:
    return {
        "visual_creative_generate": ActionSpec(
            action_type="visual_creative_generate@v1",
            action_class="ads_write",
            externally_verified=True,
            idempotent=True,
            approval_required=True,
            bounded_by_blast_radius=True,
            prod_ready=False,
            notes=(
                "DecisionCore authorizes the visual brief; the gateway only realizes it",
                "provider routing remains outside DecisionCore and inside the operator-controlled gateway",
            ),
        ),
        "visual_creative_poll": ActionSpec(
            action_type="visual_creative_poll@v1",
            action_class="read_only",
            externally_verified=False,
            idempotent=True,
            reversible=True,
            prod_ready=False,
            notes=("read-only observation of an already-authorized visual generation job",),
        ),
    }


__all__ = ["build_visual_creative_action_specs"]
