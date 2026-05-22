from __future__ import annotations

from runtime.platform.container_runtime_contract import ContainerRuntimeProbe, evaluate_container_runtime
from runtime.platform.postgres_recovery_worker_contract import PostgresRecoveryQueueItem, evaluate_recovery_queue_item


def test_recovery_worker_contract_requires_replay_dispatch_for_crash_window() -> None:
    report = evaluate_recovery_queue_item(
        PostgresRecoveryQueueItem(
            recovery_id="recovery-1",
            tenant_id="tenant-1",
            ledger_id="ledger-1",
            decision_id="decision-1",
            idempotency_key="idem-1",
            ledger_marked=True,
            dispatch_claimed=False,
            handler_dispatched=False,
            effect_verified=False,
            queued_action="replay_dispatch",
            status="pending",
        )
    )

    assert report["status"] == "ready"
    assert report["expected_action"] == "replay_dispatch"
    assert report["violations"] == []
    assert report["claims_production_ready"] is False


def test_recovery_worker_contract_blocks_wrong_action() -> None:
    report = evaluate_recovery_queue_item(
        PostgresRecoveryQueueItem(
            recovery_id="recovery-1",
            tenant_id="tenant-1",
            ledger_id="ledger-1",
            decision_id="decision-1",
            idempotency_key="idem-1",
            ledger_marked=True,
            dispatch_claimed=False,
            handler_dispatched=False,
            effect_verified=False,
            queued_action="noop_already_verified",
            status="pending",
        )
    )

    assert report["status"] == "blocked"
    assert "queued_action_mismatch" in report["violations"]


def test_container_runtime_contract_requires_readiness_surfaces() -> None:
    report = evaluate_container_runtime(
        ContainerRuntimeProbe(
            image_built=True,
            container_started=True,
            readyz_ok=True,
            storagez_ok=True,
            executionz_ok=True,
            uses_readiness_healthcheck=True,
        )
    )

    assert report["status"] == "ready"
    assert report["violations"] == []
    assert report["claims_production_ready"] is False


def test_container_runtime_contract_blocks_liveness_only_container() -> None:
    report = evaluate_container_runtime(
        ContainerRuntimeProbe(
            image_built=True,
            container_started=True,
            readyz_ok=True,
            storagez_ok=False,
            executionz_ok=False,
            uses_readiness_healthcheck=False,
        )
    )

    assert report["status"] == "blocked"
    assert "storagez_required" in report["violations"]
    assert "executionz_required" in report["violations"]
    assert "readiness_healthcheck_required" in report["violations"]
