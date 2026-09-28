from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel.decision_crypto import decision_envelope_from_recovery_snapshot
from reliability.distributed_lock import DistributedLock, build_distributed_lock
from reliability.execution_checkpoint_store import (
    CANON_CHECKPOINT_STAGE_ORDER,
    ExecutionCheckpoint,
    ExecutionCheckpointStore,
    JsonlExecutionCheckpointStore,
)
from reliability.idempotency_contract import IdempotencyKey
from reliability.idempotency_scope import build_idempotency_key, build_runtime_request_scope
from reliability.idempotency_sqlite_backend import SQLiteBackendError, SQLiteIdempotencyStore
from reliability.idempotency_store import JsonlIdempotencyStore
from reliability.leader_election import LeaderElection, LeadershipLease
from reliability.recovery_orchestrator import RecoveryOrchestrator

CANON_RUNTIME_RELIABILITY = True


def _runtime_base_dir(*, runtime_infra: Any | None = None) -> Path:
    explicit_base_dir = str(getattr(runtime_infra, "reliability_base_dir", "") or "").strip()
    if explicit_base_dir:
        return Path(explicit_base_dir)
    data_dir = str(os.getenv("DATA_DIR", "")).strip()
    if data_dir:
        return Path(data_dir)
    runtime_dir = str(os.getenv("RUNTIME_DIR", "")).strip()
    if runtime_dir:
        return Path(runtime_dir)
    decision_ledger = getattr(runtime_infra, "decision_ledger", None)
    ledger_path = str(getattr(decision_ledger, "_path", "") or "").strip()
    if ledger_path:
        return Path(ledger_path).parent / ".runtime"
    return Path(".runtime")


def _checkpoint_store_path(*, runtime_infra: Any | None = None) -> Path:
    return _runtime_base_dir(runtime_infra=runtime_infra) / 'reliability' / 'execution_checkpoints.jsonl'


def _idempotency_sqlite_path(*, runtime_infra: Any | None = None) -> Path:
    return _runtime_base_dir(runtime_infra=runtime_infra) / 'reliability' / 'idempotency_records.sqlite3'


def _idempotency_jsonl_path(*, runtime_infra: Any | None = None) -> Path:
    return _runtime_base_dir(runtime_infra=runtime_infra) / 'reliability' / 'idempotency_records.jsonl'


def normalize_tenant_id_or_unknown(value: Any) -> str:
    tenant_id = str(value or "").strip()
    return tenant_id or "unknown_tenant"


@dataclass(frozen=True)
class _OutboxAdapter:
    outbox: Any

    def get(self, *, tenant_id: str, message_id: str):
        if self.outbox is None:
            return None
        row = None
        if hasattr(self.outbox, "get"):
            try:
                row = self.outbox.get(str(message_id))
            except TypeError:
                row = self.outbox.get(tenant_id=tenant_id, message_id=str(message_id))
        elif hasattr(self.outbox, "status"):
            status = self.outbox.status(str(message_id))
            row = {"decision_id": str(message_id), "status": status, "action": "runtime.execution"}
        if row is None:
            return None
        from reliability.outbox_store import OutboxMessage, OutboxState
        status = str(row.get("status") or "pending").strip().lower()
        state_map = {
            "pending": OutboxState.PENDING,
            "delivering": OutboxState.DELIVERING,
            "inflight": OutboxState.DELIVERING,
            "delivered": OutboxState.DELIVERED,
            "dead": OutboxState.DEAD,
        }
        return OutboxMessage(
            tenant_id=str(tenant_id or "default"),
            message_id=str(row.get("message_id") or row.get("decision_id") or message_id),
            topic=str(row.get("action") or "runtime.execution"),
            dedupe_key=str(row.get("dedupe_key") or row.get("decision_id") or message_id),
            payload={"correlation_id": row.get("correlation_id"), "payload_json": row.get("payload_json")},
            state=state_map.get(status, OutboxState.PENDING),
        )


@dataclass(frozen=True)
class RuntimeReliability:
    checkpoint_store: ExecutionCheckpointStore
    idempotency_store: Any
    recovery_orchestrator: RecoveryOrchestrator
    distributed_lock: DistributedLock
    scheduler_leader_election: LeaderElection
    recovery_leader_election: LeaderElection
    tenant_default: str = "unknown_tenant"
    namespace: str = "runtime_executor"
    operation: str = "decision_execute"

    def tenant_id_for_env(self, env: Any) -> str:
        payload = getattr(getattr(env, "decision", None), "payload", None)
        if isinstance(payload, dict):
            tenant_id = normalize_tenant_id_or_unknown(payload.get("tenant_id"))
            if tenant_id:
                return tenant_id
        return normalize_tenant_id_or_unknown(self.tenant_default)

    def task_scope_for_env(
        self,
        env: Any,
    ) -> tuple[str | None, str | None, str | None, str | None]:
        payload = getattr(getattr(env, "decision", None), "payload", None)
        payload_dict = dict(payload) if isinstance(payload, dict) else {}
        business_id = str(payload_dict.get("business_id") or "").strip() or None
        task_id = str(payload_dict.get("task_id") or "").strip() or None
        task_run_id = str(payload_dict.get("task_run_id") or "").strip() or None
        step_id = str(payload_dict.get("step_id") or "").strip() or None
        if task_id is not None and business_id is None:
            raise ValueError("task-scoped execution checkpoint requires business_id")
        if task_run_id is not None and task_id is None:
            raise ValueError("task run checkpoint requires task_id")
        if step_id is not None and task_id is None:
            raise ValueError("step-scoped execution checkpoint requires task_id")
        return business_id, task_id, task_run_id, step_id

    def run_id_for_env(self, env: Any) -> str:
        decision = getattr(env, "decision", None)
        decision_id = str(getattr(decision, "decision_id", "") or "").strip()
        if decision_id:
            return decision_id
        correlation_id = str(getattr(decision, "correlation_id", "") or "").strip()
        if correlation_id:
            return correlation_id
        return hashlib.sha256(repr(env).encode("utf-8")).hexdigest()

    def idempotency_key_for_env(self, env: Any) -> IdempotencyKey:
        decision = getattr(env, 'decision', None)
        payload = getattr(decision, 'payload', None)
        payload_dict = dict(payload) if isinstance(payload, dict) else {}
        raw_key = str(payload_dict.get('idempotency_key') or getattr(decision, 'decision_id', '') or self.run_id_for_env(env)).strip()
        semantic_scope = build_runtime_request_scope(
            raw_key=raw_key,
            request_fingerprint=payload_dict.get('request_fingerprint'),
            goal=payload_dict.get('goal'),
            payload=payload_dict,
        )
        return build_idempotency_key(
            tenant_id=self.tenant_id_for_env(env),
            namespace=self.namespace,
            operation=self.operation,
            key=raw_key,
            semantic_scope=semantic_scope.as_dict(),
        )

    def reserve(self, env: Any, *, owner_id: str = "runtime-executor"):
        key = self.idempotency_key_for_env(env)
        return self.idempotency_store.reserve(key=key, owner_id=owner_id)

    def mark_completed(self, env: Any, *, owner_id: str = "runtime-executor") -> None:
        key = self.idempotency_key_for_env(env)
        record = self.idempotency_store.get(key=key)
        if record is None or record.is_terminal():
            return
        run_id = self.run_id_for_env(env)
        self.idempotency_store.mark_completed(key=key, owner_id=owner_id, result_ref=run_id, result_digest=run_id)

    def mark_failed(self, env: Any, *, owner_id: str = "runtime-executor", reason: str | None = None) -> None:
        key = self.idempotency_key_for_env(env)
        record = self.idempotency_store.get(key=key)
        if record is None or record.is_terminal():
            return
        self.idempotency_store.mark_failed(key=key, owner_id=owner_id, reason=reason)

    def plan(self, env: Any):
        key = self.idempotency_key_for_env(env)
        return self.recovery_orchestrator.plan(
            tenant_id=self.tenant_id_for_env(env),
            run_id=self.run_id_for_env(env),
            idempotency_key=key,
            outbox_message_id=self.run_id_for_env(env),
        )

    def reconcile(self, env: Any) -> dict[str, Any]:
        key = self.idempotency_key_for_env(env)
        report = self.recovery_orchestrator.reconcile(
            tenant_id=self.tenant_id_for_env(env),
            run_id=self.run_id_for_env(env),
            idempotency_key=key,
            outbox_message_id=self.run_id_for_env(env),
        )
        payload = {
            "latest_stage": getattr(report, "latest_stage", None),
            "is_clean": bool(getattr(report, "is_clean", False)),
            "anomalies": list(getattr(report, "anomalies", ()) or ()),
            "outbox_state": getattr(report, "outbox_state", None),
            "idempotency_state": getattr(report, "idempotency_state", None),
        }
        plan = self.plan(env)
        payload["recovery_plan"] = {
            "recovery_action": getattr(plan, "recovery_action", None),
            "reason": getattr(plan, "reason", None),
            "resume_action": getattr(plan, "resume_action", None),
            "resume_stage": getattr(plan, "resume_stage", None),
            "delivery_hint": getattr(plan, "delivery_hint", None),
            "operator_required": bool(getattr(plan, "operator_required", False)),
            "risk_flags": list(getattr(plan, "risk_flags", ()) or ()),
        }
        return payload

    def append_checkpoint(
        self,
        env: Any,
        *,
        stage: str,
        checkpoint_id: str,
        payload: dict[str, Any] | None = None,
        sequence_no: int | None = None,
    ) -> ExecutionCheckpoint:
        tenant_id = self.tenant_id_for_env(env)
        run_id = self.run_id_for_env(env)
        latest = self.checkpoint_store.latest(tenant_id=tenant_id, run_id=run_id)
        if (
            latest is not None
            and latest.stage != "failed"
            and stage in CANON_CHECKPOINT_STAGE_ORDER
            and latest.stage in CANON_CHECKPOINT_STAGE_ORDER
            and CANON_CHECKPOINT_STAGE_ORDER.index(stage)
            <= CANON_CHECKPOINT_STAGE_ORDER.index(latest.stage)
        ):
            return latest
        next_seq = int(sequence_no) if sequence_no is not None else (0 if latest is None else int(latest.sequence_no) + 1)
        decision = getattr(env, "decision", None)
        business_id, task_id, task_run_id, step_id = self.task_scope_for_env(env)
        cp = ExecutionCheckpoint(
            tenant_id=tenant_id,
            run_id=run_id,
            sequence_no=next_seq,
            stage=str(stage),
            checkpoint_id=str(checkpoint_id),
            decision_id=str(getattr(decision, "decision_id", "") or None) if getattr(decision, "decision_id", None) is not None else None,
            action_id=str(getattr(decision, "action", "") or None) if getattr(decision, "action", None) is not None else None,
            idempotency_key=self.idempotency_key_for_env(env).key,
            outbox_message_id=(
                str(getattr(decision, "decision_id", "") or None)
                if stage in {"execution", "verification", "state_update", "evidence"}
                and getattr(decision, "decision_id", None) is not None
                else None
            ),
            trace_id=str(getattr(decision, "correlation_id", "") or None) if getattr(decision, "correlation_id", None) is not None else None,
            business_id=business_id,
            task_id=task_id,
            task_run_id=task_run_id,
            step_id=step_id,
            payload=dict(payload or {}),
        )
        self.checkpoint_store.append(cp)
        return cp

    def plan_task_run_recovery(
        self,
        *,
        tenant_id: str,
        business_id: str,
        task_id: str,
        task_run_id: str,
    ):
        task_run = str(task_run_id or "").strip()
        if not task_run:
            raise ValueError("task_run_id is required")
        checkpoints = [
            checkpoint
            for checkpoint in self.checkpoint_store.list_task(
                tenant_id=tenant_id,
                business_id=business_id,
                task_id=task_id,
            )
            if str(checkpoint.task_run_id or checkpoint.run_id) == task_run
        ]
        if not checkpoints:
            raise LookupError(f"task run not found: {task_run}")
        latest = max(
            checkpoints,
            key=lambda item: (
                item.created_at,
                item.run_id,
                item.sequence_no,
                item.checkpoint_id,
            ),
        )
        if self.recovery_orchestrator is None:
            raise RuntimeError("canonical recovery orchestrator is not configured")
        return self.recovery_orchestrator.plan(
            tenant_id=tenant_id,
            run_id=latest.run_id,
            outbox_message_id=latest.outbox_message_id,
        )

    def recovery_envelope_for_task_run(
        self,
        *,
        tenant_id: str,
        business_id: str,
        task_id: str,
        task_run_id: str,
    ):
        checkpoints = tuple(
            checkpoint
            for checkpoint in self.checkpoint_store.list_task(
                tenant_id=tenant_id,
                business_id=business_id,
                task_id=task_id,
            )
            if str(checkpoint.task_run_id or checkpoint.run_id) == str(task_run_id)
        )
        if not checkpoints:
            raise LookupError(f"task run not found: {task_run_id}")
        latest = max(
            checkpoints,
            key=lambda item: (item.created_at, item.run_id, item.sequence_no, item.checkpoint_id),
        )
        if latest.stage not in {"decision", "executable_action"}:
            raise RuntimeError(
                "recovery envelope is only admissible from decision/executable_action, "
                f"got {latest.stage}"
            )
        raw_snapshot = dict(latest.payload or {}).get("recovery_envelope")
        if not isinstance(raw_snapshot, dict):
            raise RuntimeError(f"{latest.stage} checkpoint has no recovery envelope")
        env = decision_envelope_from_recovery_snapshot(raw_snapshot)
        decision = env.decision
        payload = dict(getattr(decision, "payload", {}) or {})
        expected = {
            "tenant_id": str(tenant_id),
            "business_id": str(business_id),
            "task_id": str(task_id),
            "task_run_id": str(task_run_id),
        }
        for name, value in expected.items():
            if str(payload.get(name) or "") != value:
                raise RuntimeError(f"recovery envelope {name} mismatch")
        if latest.decision_id and str(decision.decision_id) != str(latest.decision_id):
            raise RuntimeError("recovery envelope decision_id mismatch")
        if latest.action_id and str(decision.action) != str(latest.action_id):
            raise RuntimeError("recovery envelope action mismatch")
        return env

    def campaign_scheduler_leader(self, *, tenant_id: str, owner_id: str, ttl_seconds: int | None = None, now=None) -> LeadershipLease | None:
        return self.scheduler_leader_election.campaign(tenant_id=tenant_id, leader_id=owner_id, ttl_seconds=ttl_seconds, now=now)

    def campaign_or_heartbeat_scheduler_leader(self, *, tenant_id: str, owner_id: str, ttl_seconds: int | None = None, now=None) -> LeadershipLease | None:
        return self.scheduler_leader_election.campaign_or_heartbeat(tenant_id=tenant_id, leader_id=owner_id, ttl_seconds=ttl_seconds, now=now)

    def campaign_recovery_leader(self, *, tenant_id: str, owner_id: str, ttl_seconds: int | None = None, now=None) -> LeadershipLease | None:
        return self.recovery_leader_election.campaign(tenant_id=tenant_id, leader_id=owner_id, ttl_seconds=ttl_seconds, now=now)

    def campaign_or_heartbeat_recovery_leader(self, *, tenant_id: str, owner_id: str, ttl_seconds: int | None = None, now=None) -> LeadershipLease | None:
        return self.recovery_leader_election.campaign_or_heartbeat(tenant_id=tenant_id, leader_id=owner_id, ttl_seconds=ttl_seconds, now=now)


def _resolve_runtime_lock(*, runtime_infra: Any | None) -> DistributedLock:
    configured_backend = getattr(runtime_infra, "distributed_lock", None) if runtime_infra is not None else None
    if configured_backend is not None:
        return build_distributed_lock(backend=configured_backend)
    return build_distributed_lock(
        backend_name=getattr(runtime_infra, "distributed_lock_backend_name", None) if runtime_infra is not None else None,
        redis_url=getattr(runtime_infra, "distributed_lock_redis_url", None) if runtime_infra is not None else None,
        postgres_dsn=getattr(runtime_infra, "distributed_lock_postgres_dsn", None) if runtime_infra is not None else None,
        postgres_table_prefix=getattr(runtime_infra, "distributed_lock_postgres_table_prefix", "reliability") if runtime_infra is not None else "reliability",
        application_name=getattr(runtime_infra, "distributed_lock_application_name", "businesaios-reliability-lock") if runtime_infra is not None else "businesaios-reliability-lock",
        statement_timeout_ms=getattr(runtime_infra, "distributed_lock_statement_timeout_ms", 30000) if runtime_infra is not None else 30000,
        lock_timeout_ms=getattr(runtime_infra, "distributed_lock_lock_timeout_ms", 5000) if runtime_infra is not None else 5000,
    )


def _build_runtime_idempotency_store(*, runtime_infra: Any | None = None):
    backend_name = str(getattr(runtime_infra, 'idempotency_backend_name', None) or os.getenv('BUSINESAIOS_RUNTIME_IDEMPOTENCY_BACKEND', 'sqlite')).strip().lower()
    if backend_name == 'jsonl':
        return JsonlIdempotencyStore(_idempotency_jsonl_path(runtime_infra=runtime_infra))
    try:
        return SQLiteIdempotencyStore(_idempotency_sqlite_path(runtime_infra=runtime_infra))
    except (OSError, SQLiteBackendError):
        return JsonlIdempotencyStore(_idempotency_jsonl_path(runtime_infra=runtime_infra))


def build_runtime_reliability(*, outbox: Any, runtime_infra: Any | None = None) -> RuntimeReliability:
    checkpoint_path = _checkpoint_store_path(runtime_infra=runtime_infra)
    checkpoint_store = JsonlExecutionCheckpointStore(checkpoint_path)
    idempotency_store = _build_runtime_idempotency_store(runtime_infra=runtime_infra)
    recovery_orchestrator = RecoveryOrchestrator(
        checkpoint_store=checkpoint_store,
        idempotency_store=idempotency_store,
        outbox_store=_OutboxAdapter(outbox=outbox),
    )
    distributed_lock = _resolve_runtime_lock(runtime_infra=runtime_infra)
    scheduler_leader_election = LeaderElection(
        lock_backend=distributed_lock,
        election_name="runtime-scheduler",
        default_ttl_seconds=max(1, int(getattr(runtime_infra, "scheduler_leader_ttl_seconds", 30) if runtime_infra is not None else 30)),
    )
    recovery_leader_election = LeaderElection(
        lock_backend=distributed_lock,
        election_name="runtime-recovery",
        default_ttl_seconds=max(1, int(getattr(runtime_infra, "recovery_leader_ttl_seconds", 30) if runtime_infra is not None else 30)),
    )
    return RuntimeReliability(
        checkpoint_store=checkpoint_store,
        idempotency_store=idempotency_store,
        recovery_orchestrator=recovery_orchestrator,
        distributed_lock=distributed_lock,
        scheduler_leader_election=scheduler_leader_election,
        recovery_leader_election=recovery_leader_election,
    )


__all__ = [
    "CANON_RUNTIME_RELIABILITY",
    "RuntimeReliability",
    "build_runtime_reliability",
]
