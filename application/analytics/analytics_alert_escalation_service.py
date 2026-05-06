from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


@dataclass(frozen=True)
class AnalyticsAlertEscalationService:
    critical_escalation_level: str = 'pager'
    warning_escalation_level: str = 'operator_queue'
    info_escalation_level: str = 'log_only'

    def escalate(self, *, alerts: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for alert in alerts:
            payload = dict(alert)
            severity = str(payload.get('severity') or 'info')
            payload['escalation_level'] = self.critical_escalation_level if severity == 'critical' else self.warning_escalation_level if severity == 'warning' else self.info_escalation_level
            out.append(payload)
        return out
