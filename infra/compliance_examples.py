from __future__ import annotations

from infra.change_request import ChangeRequest
from infra.compliance_boot_result import ComplianceBootResult
from infra.policy_snapshots import build_policy_snapshot


def apply_example_change(
    compliance: ComplianceBootResult,
) -> dict:
    compliance.change_management.apply(
        ChangeRequest(
            change_id="chg-001",
            actor="operator:alice",
            change_type="feature_flag_enable",
            target_name="api.execute_action.enabled",
            payload={"value": True},
        )
    )

    compliance.operator_actions.enable_feature_flag(
        actor="operator:alice",
        name="api.execute_action.enabled",
    )

    snapshot = build_policy_snapshot(
        name="after_example_change",
        feature_flags=compliance.operator_actions.feature_flags,
        kill_switches=compliance.operator_actions.kill_switches,
        maintenance_mode=compliance.operator_actions.maintenance_mode,
    )

    return {
        "changes_count": len(compliance.change_management.list_changes()),
        "audit_events_count": len(compliance.audit_log.events()),
        "snapshot_name": snapshot.name,
    }
