from __future__ import annotations

from infra.approval_request import ApprovalRequest
from infra.governed_autonomy_boot_result import GovernedAutonomyBootResult
from infra.multi_step_approvals import evaluate_multi_step_approval
from infra.policy_versioning import PolicyVersion
from infra.release_promotion import ReleasePromotionRequest


def example_governed_promotion(
    governed: GovernedAutonomyBootResult,
) -> dict:
    governed.policy_versions.register(
        PolicyVersion(
            version_id="policy-v1",
            policy_name="release_promotion_policy",
            metadata={"scope": "release"},
        )
    )

    approval = ApprovalRequest(
        request_id="apr-001",
        actor="operator:alice",
        approval_type="release_promotion",
        target_name="release-2026-03-11",
        required_steps=("ops", "risk", "product"),
        payload={"target_stage": "prod"},
    )
    governed.approvals.submit(approval)

    governed.approvals.approve_step(
        actor="approver:ops",
        request_id="apr-001",
        step_name="ops",
    )
    governed.approvals.approve_step(
        actor="approver:risk",
        request_id="apr-001",
        step_name="risk",
    )
    governed.approvals.approve_step(
        actor="approver:product",
        request_id="apr-001",
        step_name="product",
    )

    decision = evaluate_multi_step_approval(
        required_steps=approval.required_steps,
        approved_steps=governed.approvals.store.approved_steps("apr-001"),
    )
    if not decision.approved:
        return {
            "approved": False,
            "missing_steps": list(decision.missing_steps),
        }

    governed.release_promotions.promote(
        ReleasePromotionRequest(
            promotion_id="promo-001",
            actor="operator:alice",
            release_name="release-2026-03-11",
            target_stage="prod",
            policy_version_id="policy-v1",
            approval_request_id="apr-001",
            metadata={"channel": "primary"},
        )
    )

    return {
        "approved": True,
        "ledger_entries": len(governed.decision_ledger.entries()),
    }
