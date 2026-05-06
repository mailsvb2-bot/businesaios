from __future__ import annotations

from dataclasses import dataclass

CANON_SECURITY_SLO_MODEL = True

@dataclass(frozen=True)
class SecuritySLOSnapshot:
    rotation_sla_ok: bool
    reencryption_sla_ok: bool
    incident_response_sla_ok: bool
    drill_success_rate_ok: bool


class SecuritySLOModel:
    def __init__(self, *, rotation_backlog_limit: int = 10, reencryption_backlog_limit: int = 10, incident_response_open_limit: int = 5, min_drill_success_rate: float = 0.95) -> None:
        self._rotation_backlog_limit = int(rotation_backlog_limit)
        self._reencryption_backlog_limit = int(reencryption_backlog_limit)
        self._incident_response_open_limit = int(incident_response_open_limit)
        self._min_drill_success_rate = float(min_drill_success_rate)

    def evaluate(self, *, rotation_backlog: int, reencryption_backlog: int, open_incidents: int, successful_drills: int, total_drills: int) -> SecuritySLOSnapshot:
        rate = 1.0 if total_drills <= 0 else successful_drills / float(total_drills)
        return SecuritySLOSnapshot(
            rotation_sla_ok=int(rotation_backlog) <= self._rotation_backlog_limit,
            reencryption_sla_ok=int(reencryption_backlog) <= self._reencryption_backlog_limit,
            incident_response_sla_ok=int(open_incidents) <= self._incident_response_open_limit,
            drill_success_rate_ok=rate >= self._min_drill_success_rate,
        )

__all__ = ['CANON_SECURITY_SLO_MODEL', 'SecuritySLOModel', 'SecuritySLOSnapshot']
