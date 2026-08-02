from __future__ import annotations

from types import SimpleNamespace

from config.live_canary_policy import LiveCanaryPolicy
from core.experiments.assignment import ExperimentArm, StableExperimentAssigner
from core.policies.canary import CanaryPolicyResolver


def test_policy_routing_and_evidence_assignment_use_the_same_bucket() -> None:
    policy = LiveCanaryPolicy(
        enabled=True,
        experiment_id="metro-followup-2026-08",
        assignment_secret="b" * 32,
        candidate_pct=1.0,
        allowed_tenant_ids=("tenant-a",),
        allowed_actions=("send_preapproved_message@v1",),
    )
    active = SimpleNamespace(policy_id="active@v1")
    candidate = SimpleNamespace(policy_id="candidate@v2")
    resolver = CanaryPolicyResolver(
        SimpleNamespace(active=lambda: active, canary=lambda: candidate),
        SimpleNamespace(canary_pct=0.01),
        policy,
    )
    assigner = StableExperimentAssigner(policy)

    for index in range(10_000):
        subject_id = f"customer-{index}"
        selected = resolver.resolve_policy(subject_id, tenant_id="tenant-a")
        assignment = assigner.assign(
            tenant_id="tenant-a",
            subject_id=subject_id,
            candidate_policy_id="candidate@v2",
            action="send_preapproved_message@v1",
        )
        assert (selected.policy_id == "candidate@v2") is (
            assignment.arm is ExperimentArm.CANDIDATE
        )
