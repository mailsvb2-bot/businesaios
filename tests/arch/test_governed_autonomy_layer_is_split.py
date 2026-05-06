from pathlib import Path


def test_governed_autonomy_layer_is_split() -> None:
    for rel in (
        "infra/approval_request.py",
        "infra/approval_store.py",
        "infra/approval_service.py",
        "infra/multi_step_approvals.py",
        "infra/policy_versioning.py",
        "infra/decision_ledger.py",
        "infra/release_promotion.py",
        "infra/rollback_record.py",
        "infra/rollback_service.py",
        "infra/governed_autonomy_boot.py",
        "infra/governed_autonomy_boot_result.py",
    ):
        assert Path(rel).exists(), rel
