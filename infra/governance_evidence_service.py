from __future__ import annotations

from dataclasses import dataclass, field

from infra.audit_log_service import AuditLogService
from infra.decision_packet import DecisionPacket
from infra.governance_evidence import GovernanceEvidence
from infra.operator_session_records import OperatorSessionRegistry
from infra.rollback_packet import RollbackPacket


@dataclass
class GovernanceEvidenceService:
    audit_log: AuditLogService
    sessions: OperatorSessionRegistry
    _evidence: list[GovernanceEvidence] = field(default_factory=list)
    _decision_packets: list[DecisionPacket] = field(default_factory=list)
    _rollback_packets: list[RollbackPacket] = field(default_factory=list)

    def record_evidence(self, evidence: GovernanceEvidence) -> None:
        self._evidence.append(evidence)
        self.audit_log.record(
            event_name="governance_evidence_recorded",
            actor="system",
            category="governance_evidence",
            payload={
                "evidence_id": evidence.evidence_id,
                "evidence_type": evidence.evidence_type,
            },
        )

    def record_decision_packet(self, packet: DecisionPacket) -> None:
        self._decision_packets.append(packet)
        self.audit_log.record(
            event_name="decision_packet_recorded",
            actor=packet.actor,
            category="governance_evidence",
            payload={
                "packet_id": packet.packet_id,
                "decision_name": packet.decision_name,
                "policy_version_id": packet.policy_version_id,
            },
        )

    def record_rollback_packet(self, packet: RollbackPacket) -> None:
        self._rollback_packets.append(packet)
        self.audit_log.record(
            event_name="rollback_packet_recorded",
            actor=packet.actor,
            category="governance_evidence",
            payload={
                "packet_id": packet.packet_id,
                "rollback_id": packet.rollback_id,
                "target_name": packet.target_name,
            },
        )

    def evidence(self) -> tuple[GovernanceEvidence, ...]:
        return tuple(self._evidence)

    def decision_packets(self) -> tuple[DecisionPacket, ...]:
        return tuple(self._decision_packets)

    def rollback_packets(self) -> tuple[RollbackPacket, ...]:
        return tuple(self._rollback_packets)
