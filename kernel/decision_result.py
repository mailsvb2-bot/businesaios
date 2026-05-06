from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from contracts.executable_action import ExecutableAction
from kernel.decision_candidate import DecisionCandidate
from kernel.decision_reason import DecisionReason
from kernel.decision_rejection import DecisionRejection
from kernel.decision_trace import DecisionTrace
import shared.types as _shared_types


@dataclass(frozen=True)
class DecisionResult:
    candidate: Optional[DecisionCandidate]
    reasons: List[DecisionReason] = field(default_factory=list)
    rejection: Optional[DecisionRejection] = None
    trace: Optional[DecisionTrace] = None
    executable_action: Optional[ExecutableAction] = None

    @property
    def approved(self) -> bool:
        return self.candidate is not None and self.rejection is None and self.executable_action is not None

    def as_dict(self) -> Dict[str, Any]:
        payload = {
            'approved': self.approved,
            'candidate': None if self.candidate is None else {
                'candidate_id': self.candidate.candidate_id,
                'action_type': self.candidate.action_type,
                'channel': self.candidate.channel,
                'score': self.candidate.score,
                'expected_value': self.candidate.expected_value,
                'confidence': self.candidate.confidence,
                'reasons': list(self.candidate.reasons),
                'payload': self.candidate.normalized_payload(),
            },
            'reasons': [{'code': item.code, 'message': item.message} for item in self.reasons],
            'rejection': None if self.rejection is None else {
                'reason_code': self.rejection.reason_code,
                'message': self.rejection.message,
            },
            'trace': None if self.trace is None else {
                'request_id': self.trace.request_id,
                'decision_id': self.trace.decision_id,
                'steps': list(self.trace.steps),
                'metadata': dict(self.trace.metadata),
            },
            'executable_action': None if self.executable_action is None else self.executable_action.as_dict(),
        }
        return _shared_types.ensure_jsonable(payload)
