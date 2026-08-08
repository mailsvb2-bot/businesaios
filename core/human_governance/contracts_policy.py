from __future__ import annotations

from typing import Protocol

from .enums import RiskLevel, SalesHandoffReason
from .types import ApprovalDecision, OverrideRecord


class HumanGovernancePolicyContract(Protocol):
    def is_terminal(self, status: str) -> bool: ...

    def is_open_queue_status(self, status: str) -> bool: ...

    def needs_approval(self, status: str) -> bool: ...

    def ensure_actionable(self, status: str) -> None: ...

    def validate_actor_id(self, actor_id: str) -> str: ...

    def validate_reason(self, reason: str) -> str: ...

    def validate_approval_decision(self, decision: ApprovalDecision) -> ApprovalDecision: ...

    def validate_override_record(self, record: OverrideRecord) -> OverrideRecord: ...

    def evaluate_sales_handoff(
        self,
        *,
        model_confidence: float,
        explicit_human_request: bool,
        sensitive_context: bool,
        pricing_exception: bool,
        negative_sentiment: bool,
        failed_attempts: int,
        subject_closed: bool,
    ) -> tuple[SalesHandoffReason, RiskLevel, str] | None: ...
