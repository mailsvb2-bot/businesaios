from __future__ import annotations

from infra.approval_evidence_links import ApprovalEvidenceLink
from infra.constitutional_evidence import ConstitutionalEvidence
from infra.decision_packet import DecisionPacket
from infra.governance_evidence import GovernanceEvidence
from infra.governance_evidence_boot_result import GovernanceEvidenceBootResult
from infra.operator_session_records import OperatorSessionRecord
from infra.policy_snapshot_evidence import PolicySnapshotEvidence
from infra.rollback_packet import RollbackPacket


def example_record_governance_packets(
    evidence_boot: GovernanceEvidenceBootResult,
) -> dict:
    evidence_boot.sessions.register(
        OperatorSessionRecord(
            session_id="sess-001",
            actor="operator:alice",
            actor_scope="ops",
            metadata={"channel": "console"},
        )
    )

    evidence_boot.service.record_evidence(
        GovernanceEvidence(
            evidence_id="ev-001",
            evidence_type="operator_session_started",
            payload={"session_id": "sess-001"},
        )
    )

    decision_packet = DecisionPacket(
        packet_id="pkt-001",
        decision_name="release_promotion",
        actor="operator:alice",
        policy_version_id="policy-v1",
        approval=ApprovalEvidenceLink(
            request_id="apr-001",
            required_steps=("ops", "risk", "product"),
            approved_steps=("ops", "risk", "product"),
            fully_approved=True,
        ),
        policy_snapshot=PolicySnapshotEvidence(
            snapshot_name="pre_release_promotion",
            feature_flags={"api.execute_action.enabled": True},
            kill_switches={"api.execute_action": False},
            maintenance_mode_enabled=False,
            maintenance_reason=None,
        ),
        constitutional=ConstitutionalEvidence(
            action_name="release.promote.prod",
            actor_scope="ops",
            allowed=True,
            reasons=(),
            escalation_route=("ops", "risk", "executive"),
        ),
        metadata={"release_name": "release-2026-03-11"},
    )
    evidence_boot.service.record_decision_packet(decision_packet)

    rollback_packet = RollbackPacket(
        packet_id="rbpkt-001",
        rollback_id="rb-001",
        actor="operator:bob",
        target_name="release-2026-03-11",
        reason="conversion_drop_detected",
        policy_version_id="policy-v1",
        policy_snapshot=PolicySnapshotEvidence(
            snapshot_name="pre_rollback",
            feature_flags={"api.execute_action.enabled": True},
            kill_switches={"api.execute_action": False},
            maintenance_mode_enabled=False,
            maintenance_reason=None,
        ),
        constitutional=ConstitutionalEvidence(
            action_name="rollback.execute.prod",
            actor_scope="ops",
            allowed=True,
            reasons=(),
            escalation_route=(),
        ),
        metadata={"severity": "high"},
    )
    evidence_boot.service.record_rollback_packet(rollback_packet)

    return {
        "sessions": len(evidence_boot.sessions.list_sessions()),
        "evidence_records": len(evidence_boot.service.evidence()),
        "decision_packets": len(evidence_boot.service.decision_packets()),
        "rollback_packets": len(evidence_boot.service.rollback_packets()),
    }
