from __future__ import annotations

from typing import Protocol

from .types import ApprovalDecision, ApprovalState, OverrideRecord


class ApprovalWriter(Protocol):
    def write_approval(self, decision: ApprovalDecision) -> ApprovalState: ...


class RejectionWriter(Protocol):
    def write_rejection(self, decision: ApprovalDecision) -> ApprovalState: ...


class OverrideWriter(Protocol):
    def write_override(self, record: OverrideRecord) -> OverrideRecord: ...


class PauseWriter(Protocol):
    def write_pause(self, review_id: str, reason: str, actor_id: str) -> ApprovalState: ...
