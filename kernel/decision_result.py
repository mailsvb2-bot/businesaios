from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import shared.types as _shared_types
from contracts.executable_action import ExecutableAction
from kernel.decision_candidate import DecisionCandidate
from kernel.decision_reason import DecisionReason
from kernel.decision_rejection import DecisionRejection
from kernel.decision_trace import DecisionTrace


@dataclass(frozen=True)
class DecisionResult:
    """Result of recommendation-space narrowing, never execution authority."""

    candidate: Optional[DecisionCandidate]
    reasons: List[DecisionReason] = field(default_factory=list)
    rejection: Optional[DecisionRejection] = None
    trace: Optional[DecisionTrace] = None
    # Retained only for historical deserialization/API shape. Canonical
    # recommendation services must leave this field empty; executable authority
    # exists only in a signed runtime DecisionEnvelope.
    executable_action: Optional[ExecutableAction] = None

    @property
    def recommended(self) -> bool:
        return self.candidate is not None and self.rejection is None

    @property
    def approved(self) -> bool:
        """Compatibility alias for a successful recommendation, not execution."""

        return self.recommended

    def as_dict(self) -> Dict[str, Any]:
        payload = {
            "approved": self.approved,
            "recommended": self.recommended,
            "executable": False,
            "candidate": None
            if self.candidate is None
            else {
                "candidate_id": self.candidate.candidate_id,
                "action_type": self.candidate.action_type,
                "channel": self.candidate.channel,
                "score": self.candidate.score,
                "expected_value": self.candidate.expected_value,
                "confidence": self.candidate.confidence,
                "reasons": list(self.candidate.reasons),
                "payload": self.candidate.normalized_payload(),
            },
            "reasons": [
                {"code": item.code, "message": item.message}
                for item in self.reasons
            ],
            "rejection": None
            if self.rejection is None
            else {
                "reason_code": self.rejection.reason_code,
                "message": self.rejection.message,
            },
            "trace": None
            if self.trace is None
            else {
                "request_id": self.trace.request_id,
                "decision_id": self.trace.decision_id,
                "steps": list(self.trace.steps),
                "metadata": dict(self.trace.metadata),
            },
            "executable_action": None,
        }
        return _shared_types.ensure_jsonable(payload)
