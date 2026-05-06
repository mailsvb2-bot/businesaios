from __future__ import annotations

"""Reliability / recovery / crash-safety primitives.

Infra-only namespace.
Must never become a second decision center.
"""

from reliability.dead_letter_policy import DeadLetterDecision, DeadLetterPolicy
from reliability.distributed_lock import DistributedLock, InMemoryDistributedLock, LockLease, PluggableDistributedLock, build_distributed_lock
from reliability.distributed_lock_backend import DistributedLockBackend, LockBackendRecord
from reliability.distributed_lock_postgres import PostgresDistributedLockBackend
from reliability.distributed_lock_redis import RedisDistributedLockBackend
from reliability.execution_checkpoint_store import (
    CANON_CHECKPOINT_STAGE_ORDER,
    ExecutionCheckpoint,
    ExecutionCheckpointStore,
    InMemoryExecutionCheckpointStore,
    JsonlExecutionCheckpointStore,
)
from reliability.execution_reconciliation import ExecutionReconciliation, ReconciliationReport
from reliability.idempotency_backend import BaseBackendIdempotencyStore, IdempotencyBackend
from reliability.idempotency_contract import (
    IdempotencyDecision,
    IdempotencyKey,
    IdempotencyRecord,
    IdempotencyResolution,
    IdempotencyState,
    IdempotencyStore,
)
from reliability.idempotency_scope import IdempotencyScope, build_evidence_persistence_scope, build_headless_scope, build_idempotency_key, build_runtime_request_scope
from reliability.idempotency_sqlite_backend import SQLiteIdempotencyBackend, SQLiteIdempotencyStore
from reliability.idempotency_store import InMemoryIdempotencyStore, JsonlIdempotencyStore
from reliability.inbox_dedup import InboxDedup, InboxReceipt
from reliability.job_recovery_policy import JobRecoveryDecision, JobRecoveryPolicy
from reliability.lease_manager import LeaseHeartbeat, LeaseManager
from reliability.leader_election import LeaderElection, LeadershipLease
from reliability.lease_fencing_token import LeaseFencingToken, assert_fencing_token_progression
from reliability.outbox_store import InMemoryOutboxStore, OutboxMessage, OutboxState, OutboxStore
from reliability.outbox_backend import (
    OutboxBackend,
    OutboxBackendHealth,
    OutboxBackendInspector,
    OutboxBackendMode,
    OutboxDeliveryConflict,
    OutboxDeliveryError,
    OutboxDeliveryReceipt,
    OutboxDeliveryRecord,
    OutboxDeliveryStatus,
)
from reliability.outbox_delivery_worker import (
    OutboxDeliveryAttemptReport,
    OutboxDeliveryRunReport,
    OutboxDeliveryWorker,
)
from reliability.outbox_worker_contract import (
    GlobalOutboxDeliveryReport,
    GlobalOutboxWorker,
    OutboxWorkerDescriptor,
)
from reliability.outbox_file_backend import FileOutboxBackend
from reliability.outbox_reconciliation import (
    OutboxReconciliation,
    OutboxReconciliationFinding,
    OutboxReconciliationReport,
)
from reliability.outbox_sqlite_backend import SQLiteOutboxBackend
from reliability.recovery_execution_graph import (
    RecoveryExecutionEdge,
    RecoveryExecutionGraph,
    RecoveryExecutionNode,
    RecoveryGraphValidationReport,
    RecoveryResumePoint,
    build_canonical_recovery_execution_graph,
)
from reliability.recovery_orchestrator import RecoveryOrchestrator, RecoveryPlan, TransportRecoveryResult
from reliability.recovery_policy_engine import (
    RecoveryPolicyConfig,
    RecoveryPolicyDecision,
    RecoveryPolicyEngine,
)
from reliability.recovery_run_rebuilder import RebuiltRunFacts, RecoveryRunRebuilder
from reliability.replay_guard import ReplayGuard, ReplayVerdict

CANON_RELIABILITY_PUBLIC_API = True

__all__ = [
    "CANON_CHECKPOINT_STAGE_ORDER",
    "CANON_RELIABILITY_PUBLIC_API",
    "DeadLetterDecision",
    "DeadLetterPolicy",
    "DistributedLock",
    "DistributedLockBackend",
    "ExecutionCheckpoint",
    "ExecutionCheckpointStore",
    "ExecutionReconciliation",
    "BaseBackendIdempotencyStore",
    "IdempotencyBackend",
    "IdempotencyScope",
    "IdempotencyDecision",
    "IdempotencyKey",
    "IdempotencyRecord",
    "IdempotencyResolution",
    "IdempotencyState",
    "IdempotencyStore",
    "InMemoryDistributedLock",
    "LockBackendRecord",
    "InMemoryExecutionCheckpointStore",
    "InMemoryIdempotencyStore",
    "InMemoryOutboxStore",
    "InboxDedup",
    "InboxReceipt",
    "JobRecoveryDecision",
    "JobRecoveryPolicy",
    "JsonlExecutionCheckpointStore",
    "SQLiteIdempotencyBackend",
    "SQLiteIdempotencyStore",
    "JsonlIdempotencyStore",
    "LeaderElection",
    "LeadershipLease",
    "LeaseFencingToken",
    "LeaseHeartbeat",
    "LeaseManager",
    "LockLease",
    "OutboxMessage",
    "SQLiteOutboxBackend",
    "FileOutboxBackend",
    "OutboxReconciliationReport",
    "OutboxReconciliationFinding",
    "OutboxReconciliation",
    "OutboxDeliveryWorker",
    "GlobalOutboxDeliveryReport",
    "GlobalOutboxWorker",
    "OutboxWorkerDescriptor",
    "OutboxDeliveryStatus",
    "OutboxDeliveryRunReport",
    "OutboxDeliveryRecord",
    "OutboxDeliveryReceipt",
    "OutboxDeliveryError",
    "OutboxDeliveryConflict",
    "OutboxDeliveryAttemptReport",
    "OutboxBackendMode",
    "OutboxBackendInspector",
    "OutboxBackendHealth",
    "OutboxBackend",
    "PostgresDistributedLockBackend",
    "OutboxState",
    "OutboxStore",
    "PluggableDistributedLock",
    "RebuiltRunFacts",
    "RecoveryExecutionEdge",
    "RecoveryExecutionGraph",
    "RecoveryExecutionNode",
    "RecoveryGraphValidationReport",
    "RecoveryPolicyConfig",
    "RecoveryPolicyDecision",
    "RecoveryPolicyEngine",
    "RecoveryResumePoint",
    "RecoveryRunRebuilder",
    "build_canonical_recovery_execution_graph",
    "RecoveryOrchestrator",
    "RecoveryPlan",
    "TransportRecoveryResult",
    "ReconciliationReport",
    "RedisDistributedLockBackend",
    "ReplayGuard",
    "ReplayVerdict",
    "assert_fencing_token_progression",
    "build_distributed_lock",
    "build_evidence_persistence_scope",
    "build_headless_scope",
    "build_idempotency_key",
    "build_runtime_request_scope",
]
