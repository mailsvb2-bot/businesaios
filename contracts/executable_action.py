from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True)
class ExecutableAction:
    action_id: str
    action_type: str
    channel: str
    payload: Dict[str, Any] = field(default_factory=dict)
    decision_id: str = ''
    correlation_id: str = ''
    objective_name: str = 'profit_adjusted_growth'

    def validate_contract(self) -> list[str]:
        issues: list[str] = []
        if not self.action_id:
            issues.append('missing:action_id')
        if not self.action_type or self.action_type.strip() != self.action_type:
            issues.append('invalid:action_type')
        if not self.channel:
            issues.append('missing:channel')
        if not isinstance(self.payload, dict):
            issues.append('invalid:payload')
        if not self.decision_id:
            issues.append('missing:decision_id')
        if not self.correlation_id:
            issues.append('missing:correlation_id')
        if self.objective_name != 'profit_adjusted_growth':
            issues.append('invalid:objective_name')
        return issues

    def as_dict(self) -> Dict[str, Any]:
        return {
            'action_id': self.action_id,
            'action_type': self.action_type,
            'channel': self.channel,
            'payload': dict(self.payload),
            'decision_id': self.decision_id,
            'correlation_id': self.correlation_id,
            'objective_name': self.objective_name,
        }
