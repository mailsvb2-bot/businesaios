from __future__ import annotations

import logging
from typing import Any

from application.autonomy.autonomy_safety_bundle import AutonomySafetyBundle
from application.evidence.evidence_verifier import EvidenceVerifier
from execution.action_budget_engine import ActionBudgetEngine
from execution.blast_radius_guard import BlastRadiusGuard
from execution.bounded_autonomy import BoundedAutonomyGuard
from observability.decision_trace_store import NullDecisionTraceStore
from runtime.executor_runtime_support import build_executor_queue_support

CANON_RUNTIME_EXECUTOR_POST_INIT_BINDINGS = True
_LOGGER = logging.getLogger("runtime.executor")


def bind_executor_post_init_surfaces(
    *,
    executor: Any,
    runtime_infra: Any,
    operational_budget_service: Any,
    queue_store: Any,
    queue_dead_letter_store: Any,
    queue_dispatcher: Any,
    queue_scheduler: Any,
    queue_worker: Any,
    queue_runner: Any,
    queue_rate_limit_guard: Any,
    queue_backpressure_policy: Any,
    queue_throttle_policy: Any,
    queue_retry_policy: Any,
    queue_worker_id: str,
    tenant_runtime_isolation: Any,
    tenant_execution_budget_guard: Any,
    action_audit_log: Any,
    execution_trace_store: Any,
    decision_trace_store: Any,
    runtime_effect_trace_store: Any,
) -> None:
    executor._operational_budget_service = operational_budget_service
    executor._governance_execution_guard = None
    executor._action_budget_engine = ActionBudgetEngine()
    executor._blast_radius_guard = BlastRadiusGuard(action_budget_engine=executor._action_budget_engine)
    executor._bounded_autonomy_guard = BoundedAutonomyGuard(action_budget_engine=executor._action_budget_engine)
    executor._autonomy_safety_bundle = AutonomySafetyBundle(
        action_budget_engine=executor._action_budget_engine,
        blast_radius_guard=executor._blast_radius_guard,
        bounded_autonomy_guard=executor._bounded_autonomy_guard,
    )
    executor._tenant_runtime_isolation = tenant_runtime_isolation or getattr(runtime_infra, "tenant_runtime_isolation", None)
    executor._tenant_execution_budget_guard = tenant_execution_budget_guard or getattr(runtime_infra, "tenant_execution_budget_guard", None)
    executor._tenant_registry = getattr(runtime_infra, "tenant_registry", None)
    executor._runtime_observability = getattr(runtime_infra, "runtime_observability", None)
    executor._inference_budget_burn_log = getattr(runtime_infra, "inference_budget_burn_log", None)
    executor._runtime_owner_id = str(queue_worker_id or getattr(runtime_infra, "runtime_owner_id", None) or "runtime-executor").strip() or "runtime-executor"
    executor._action_audit_log = action_audit_log or getattr(runtime_infra, "action_audit_log", None)
    executor._execution_trace_store = execution_trace_store or getattr(runtime_infra, "execution_trace_store", None)
    executor._decision_trace_store = getattr(runtime_infra, "decision_trace_store", None) or decision_trace_store or NullDecisionTraceStore()
    executor._runtime_effect_trace_store = runtime_effect_trace_store or getattr(runtime_infra, "runtime_effect_trace_store", None)
    executor._connector_observability = getattr(runtime_infra, "connector_observability", None)
    executor._connector_health_monitor = getattr(runtime_infra, "connector_health_monitor", None)
    executor._connector_failover_router = getattr(runtime_infra, "connector_failover_router", None)
    executor._evidence_verifier = getattr(runtime_infra, "evidence_verifier", None) or EvidenceVerifier()
    executor._logger = _LOGGER
    executor._queue_support = build_executor_queue_support(
        runtime_infra=runtime_infra,
        queue_store=queue_store,
        queue_dead_letter_store=queue_dead_letter_store,
        queue_dispatcher=queue_dispatcher,
        queue_scheduler=queue_scheduler,
        queue_worker=queue_worker,
        queue_runner=queue_runner,
        queue_rate_limit_guard=queue_rate_limit_guard,
        queue_backpressure_policy=queue_backpressure_policy,
        queue_throttle_policy=queue_throttle_policy,
        queue_retry_policy=queue_retry_policy,
        worker_id=str(queue_worker_id or "runtime-executor"),
    )


__all__ = ["CANON_RUNTIME_EXECUTOR_POST_INIT_BINDINGS", "bind_executor_post_init_surfaces"]
