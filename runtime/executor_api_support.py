from __future__ import annotations

import runtime.execution.executor_trace_runtime as trace_runtime
from runtime.decision import DecisionEnvelope
from runtime.execution.context import assert_called_from_executor, executor_context
from runtime.execution.executor_autonomy_gate import (
    deny_autonomy_execution as executor_deny_autonomy_execution,
)
from runtime.execution.executor_autonomy_gate import (
    enforce_runtime_budget_and_blast_radius as executor_enforce_runtime_budget_and_blast_radius,
)
from runtime.execution.executor_autonomy_gate import (
    ensure_tenant_runtime_contracts as executor_ensure_tenant_runtime_contracts,
)
from runtime.execution.executor_autonomy_gate import (
    tenant_runtime_context as executor_tenant_runtime_context,
)
from runtime.execution.executor_queue_runtime import (
    campaign_or_heartbeat_recovery_leader as executor_campaign_or_heartbeat_recovery_leader,
)
from runtime.execution.executor_queue_runtime import (
    campaign_or_heartbeat_scheduler_leader as executor_campaign_or_heartbeat_scheduler_leader,
)
from runtime.execution.executor_queue_runtime import (
    campaign_recovery_leader as executor_campaign_recovery_leader,
)
from runtime.execution.executor_queue_runtime import (
    campaign_scheduler_leader as executor_campaign_scheduler_leader,
)
from runtime.execution.executor_queue_runtime import (
    enqueue_runtime_job as executor_enqueue_runtime_job,
)
from runtime.execution.executor_queue_runtime import (
    run_queue_tick as executor_run_queue_tick,
)
from runtime.execution.executor_queue_runtime import (
    run_queue_tick_as_leader as executor_run_queue_tick_as_leader,
)
from runtime.execution.executor_stages import dispatch_effects
from runtime.execution.executor_stages import preflight_and_verify as _preflight_and_verify


def preflight_and_verify(*args, **kwargs):
    return _preflight_and_verify(*args, **kwargs)


def execute_core_flow(*, executor, env, depth, timescale):
    return trace_runtime.execute_core_flow(
        executor=executor,
        env=env,
        depth=depth,
        timescale=timescale,
        preflight_fn=preflight_and_verify,
    )


def _ensure_tenant_runtime_contracts(self, tenant_id: str) -> None:
    executor_ensure_tenant_runtime_contracts(executor=self, tenant_id=tenant_id)


def _tenant_runtime_context(self, *, env: DecisionEnvelope, payload):
    return executor_tenant_runtime_context(executor=self, env=env, payload=payload)


def _deny_autonomy_execution(self, *, env: DecisionEnvelope, reason: str, payload=None) -> None:
    executor_deny_autonomy_execution(executor=self, env=env, reason=reason, payload=payload)


def _enforce_runtime_budget_and_blast_radius(self, env: DecisionEnvelope):
    return executor_enforce_runtime_budget_and_blast_radius(executor=self, env=env)


def _dispatch(self, env: DecisionEnvelope, *, depth: int, enqueue: bool):
    return dispatch_effects(executor=self, env=env, depth=depth, enqueue=enqueue)


def enqueue_runtime_job(self, request):
    return executor_enqueue_runtime_job(executor=self, request=request)


def run_queue_tick(self, *, tenant_id: str, queue_name: str, now=None):
    return executor_run_queue_tick(executor=self, tenant_id=tenant_id, queue_name=queue_name, now=now)


def campaign_scheduler_leader(self, *, tenant_id: str, owner_id: str, ttl_seconds: int | None = None, now=None):
    return executor_campaign_scheduler_leader(executor=self, tenant_id=tenant_id, owner_id=owner_id, ttl_seconds=ttl_seconds, now=now)


def campaign_or_heartbeat_scheduler_leader(self, *, tenant_id: str, owner_id: str, ttl_seconds: int | None = None, now=None):
    return executor_campaign_or_heartbeat_scheduler_leader(executor=self, tenant_id=tenant_id, owner_id=owner_id, ttl_seconds=ttl_seconds, now=now)


def campaign_recovery_leader(self, *, tenant_id: str, owner_id: str, ttl_seconds: int | None = None, now=None):
    return executor_campaign_recovery_leader(executor=self, tenant_id=tenant_id, owner_id=owner_id, ttl_seconds=ttl_seconds, now=now)


def campaign_or_heartbeat_recovery_leader(self, *, tenant_id: str, owner_id: str, ttl_seconds: int | None = None, now=None):
    return executor_campaign_or_heartbeat_recovery_leader(executor=self, tenant_id=tenant_id, owner_id=owner_id, ttl_seconds=ttl_seconds, now=now)


def run_queue_tick_as_leader(self, *, tenant_id: str, queue_name: str, owner_id: str, ttl_seconds: int | None = None, now=None):
    return executor_run_queue_tick_as_leader(
        executor=self,
        tenant_id=tenant_id,
        queue_name=queue_name,
        owner_id=owner_id,
        ttl_seconds=ttl_seconds,
        now=now,
    )


__all__ = [
    'preflight_and_verify',
    'execute_core_flow',
    'executor_context',
    'assert_called_from_executor',
    '_ensure_tenant_runtime_contracts',
    '_tenant_runtime_context',
    '_deny_autonomy_execution',
    '_enforce_runtime_budget_and_blast_radius',
    '_dispatch',
    'enqueue_runtime_job',
    'run_queue_tick',
    'campaign_scheduler_leader',
    'campaign_or_heartbeat_scheduler_leader',
    'campaign_recovery_leader',
    'campaign_or_heartbeat_recovery_leader',
    'run_queue_tick_as_leader',
]
