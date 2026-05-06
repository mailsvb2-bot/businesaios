from __future__ import annotations

from infra.compliance_boot_result import ComplianceBootResult


def activate_incident(
    compliance: ComplianceBootResult,
    *,
    actor: str,
    incident_id: str,
) -> dict:
    compliance.incident_mode.activate(incident_id=incident_id)
    compliance.audit_log.record(
        event_name="incident_mode_activated",
        actor=actor,
        category="incident_management",
        payload={"incident_id": incident_id},
    )

    return {
        "incident_mode_enabled": compliance.incident_mode.is_enabled(),
        "incident_id": compliance.incident_mode.incident_id(),
    }
