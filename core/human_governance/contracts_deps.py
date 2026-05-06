from __future__ import annotations

from dataclasses import dataclass

from .contracts_policy import HumanGovernancePolicyContract
from .contracts_readers import ApprovalStateReader, EscalationReader, ReviewQueueReader
from .contracts_repositories import OverrideRepository, ReviewRepository
from .contracts_writers import ApprovalWriter, OverrideWriter, PauseWriter, RejectionWriter


@dataclass(frozen=True)
class HumanGovernanceDeps:
    policy: HumanGovernancePolicyContract
    review_queue_reader: ReviewQueueReader
    approval_state_reader: ApprovalStateReader
    escalation_reader: EscalationReader
    approval_writer: ApprovalWriter
    rejection_writer: RejectionWriter
    override_writer: OverrideWriter
    pause_writer: PauseWriter
    review_repository: ReviewRepository
    override_repository: OverrideRepository
