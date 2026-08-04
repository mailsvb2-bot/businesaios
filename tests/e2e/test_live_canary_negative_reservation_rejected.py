from __future__ import annotations

from contextlib import nullcontext

import pytest

from config.live_canary_policy import LiveCanaryPolicy
from runtime.experiments.live_canary import LiveCanaryCoordinator


class Registry:
    def rollout_config(self):
        return "candidate@v2", 1

    def live_canary_assignment_window(self):
        return nullcontext()


class SpyLedger:
    def __init__(self) -> None:
        self.assignment_writes = 0

    def record_assignment(self, *_args, **_kwargs):
        self.assignment_writes += 1


class SpySafety:
    def ensure_loaded(self) -> None:
        raise AssertionError("safety materializer must not run")


def test_negative_expected_cost_is_rejected_before_assignment_evidence() -> None:
    policy = LiveCanaryPolicy(
        enabled=True,
        experiment_id="negative-reservation",
        candidate_policy_id="candidate@v2",
        assignment_secret="s" * 32,
        candidate_pct=1.0,
        max_candidate_pct=1.0,
        initial_canary_pct=1,
        allowed_tenant_ids=("tenant-a",),
    )
    coordinator = LiveCanaryCoordinator(
        event_log=object(),
        policy_registry=Registry(),
        candidate_policy_id="candidate@v2",
        policy=policy,
    )
    ledger = SpyLedger()
    coordinator.ledger = ledger
    coordinator._assignment_safety = SpySafety()

    with pytest.raises(
        RuntimeError,
        match="LIVE_CANARY_RESERVATION_COST_NEGATIVE",
    ):
        coordinator.assign(
            tenant_id="tenant-a",
            subject_id="customer-1",
            decision_id="decision-1",
            correlation_id="correlation-1",
            production_policy_id="active@v1",
            action="send_message@v1",
            purpose="live_canary",
            eligible=True,
            expected_cost=-25.0,
        )

    assert ledger.assignment_writes == 0
