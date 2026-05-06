from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass(frozen=True)
class RollbackAction:
    action: str
    payload: dict[str, object]


class RollbackExecutionState(str, Enum):
    PLANNED = 'planned'
    CONFIRMED = 'confirmed'
    EXECUTING = 'executing'
    PARTIAL = 'partial'
    EXECUTED = 'executed'
    COMPLETED = 'completed'
    FAILED = 'failed'


class RollbackReconciliationState(str, Enum):
    PENDING = 'pending'
    VERIFIED = 'verified'
    DRIFTED = 'drifted'


@dataclass(frozen=True)
class RollbackReceipt:
    step_index: int
    action: str
    status: str
    details: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class RollbackPlan:
    source_action: str
    steps: tuple[RollbackAction, ...] = field(default_factory=tuple)
    execution_state: RollbackExecutionState = RollbackExecutionState.PLANNED
    confirmation_token: str = ''
    receipts: tuple[RollbackReceipt, ...] = field(default_factory=tuple)
    reconciliation_state: RollbackReconciliationState = RollbackReconciliationState.PENDING
    reconciliation_error: str = ''
    version: int = 0
    lease_owner: str = ''
    fencing_token: int = 0
