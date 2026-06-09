from __future__ import annotations

"""Compatibility shim. Canonical owner: runtime.execution.executor_state.

This shim stays executable rather than acting as a passive re-export so that
legacy tests and monkeypatches targeting ``runtime.executor_runtime_support``
still intercept the executor assembly path. The true construction logic remains
owned by ``runtime.execution.executor_state``.

Queue support added here is strictly operational: it can persist and execute
already-authorized work, but it never decides what should be done.
"""

from dataclasses import dataclass
from typing import Any

from runtime.execution.executor_state import (
    RuntimeExecutorPorts,
    RuntimeExecutorState,
    build_executor_runtime_infra_from_runtime_infra,
    emit_throttled_executor_warning,
    resolve_executor_constitution,
    resolve_executor_economic_layer,
)
from runtime.execution.executor_state import (
    build_runtime_infra as _build_runtime_infra,
)
from runtime.execution.reliability_runtime import RuntimeReliability, build_runtime_reliability
from runtime.executor_effects import build_runtime_executor_effects
from runtime.queue.backpressure_policy import BackpressurePolicy
from runtime.queue.job_dead_letter_store import (
    JobDeadLetterStore,
    build_default_job_dead_letter_store,
)
from runtime.queue.job_dispatcher import JobDispatcher
from runtime.queue.job_retry_policy import JobRetryPolicy
from runtime.queue.job_scheduler import JobScheduler
from runtime.queue.job_store import JobStore, build_default_job_store
from runtime.queue.job_worker import JobRunner, JobWorker
from runtime.queue.rate_limit_guard import RateLimitGuard
from runtime.queue.throttle_policy import ThrottlePolicy

CANON_RUNTIME_EXECUTOR_QUEUE_SUPPORT = True


@dataclass(frozen=True)
class RuntimeExecutorQueueSupport:
    store: JobStore
    dead_letter_store: JobDeadLetterStore
    dispatcher: JobDispatcher
    scheduler: JobScheduler
    worker: JobWorker
    rate_limit_guard: RateLimitGuard
    backpressure_policy: BackpressurePolicy
    throttle_policy: ThrottlePolicy
    retry_policy: JobRetryPolicy


@dataclass(frozen=True)
class RuntimeExecutorRecoverySupport:
    reliability: RuntimeReliability
    recovery_orchestrator: Any
    checkpoint_store: Any
    idempotency_store: Any
    distributed_lock: Any
    scheduler_leader_election: Any | None = None
    recovery_leader_election: Any | None = None



def build_runtime_infra(**kwargs):
    return _build_runtime_infra(**kwargs)



def build_executor_effects_bundle(*, event_log, policy_registry, infra):
    return build_runtime_executor_effects(
        event_log=event_log,
        policy_registry=policy_registry,
        delivery_state=infra.delivery_state,
        ledger=infra.decision_ledger,
        payment_outbox=infra.payments_outbox,
        telegram_outbound_queue=infra.telegram_outbound_queue,
        settings_gateway=infra.settings_store,
        messaging_policy_event_store=infra.messaging_policy_store,
        messaging_policy_read_service=infra.messaging_policy_reader,
        http_transport=infra.http_transport,
        effect_router=infra.effect_router,
    )



def build_executor_recovery_support(
    *,
    runtime_infra: Any | None = None,
    outbox: Any | None = None,
) -> RuntimeExecutorRecoverySupport:
    """Build canonical recovery support without introducing a second brain.

    This exposes recovery primitives already derived from the canonical runtime
    reliability bundle. It does not invent new planning or policy surfaces.
    """

    resolved_outbox = outbox or getattr(runtime_infra, "effect_outbox", None) or getattr(runtime_infra, "outbox", None)
    reliability = build_runtime_reliability(outbox=resolved_outbox, runtime_infra=runtime_infra)
    return RuntimeExecutorRecoverySupport(
        reliability=reliability,
        recovery_orchestrator=reliability.recovery_orchestrator,
        checkpoint_store=reliability.checkpoint_store,
        idempotency_store=reliability.idempotency_store,
        distributed_lock=reliability.distributed_lock,
        scheduler_leader_election=getattr(reliability, "scheduler_leader_election", None),
        recovery_leader_election=getattr(reliability, "recovery_leader_election", None),
    )


def build_executor_queue_support(
    *,
    runtime_infra: Any | None = None,
    queue_store: JobStore | None = None,
    queue_dead_letter_store: JobDeadLetterStore | None = None,
    queue_dispatcher: JobDispatcher | None = None,
    queue_scheduler: JobScheduler | None = None,
    queue_worker: JobWorker | None = None,
    queue_runner: JobRunner | None = None,
    queue_rate_limit_guard: RateLimitGuard | None = None,
    queue_backpressure_policy: BackpressurePolicy | None = None,
    queue_throttle_policy: ThrottlePolicy | None = None,
    queue_retry_policy: JobRetryPolicy | None = None,
    worker_id: str = "runtime-executor",
) -> RuntimeExecutorQueueSupport:
    """Build an operational queue bundle for RuntimeExecutor.

    This is optional support. It does not replace the canonical outbox/effect
    path and must not become a second decision center.
    """

    infra = runtime_infra
    store = (
        queue_store
        or getattr(infra, "job_queue_store", None)
        or getattr(infra, "queue_store", None)
        or build_default_job_store()
    )
    dead_letter_store = (
        queue_dead_letter_store
        or getattr(infra, "job_dead_letter_store", None)
        or getattr(infra, "queue_dead_letter_store", None)
        or build_default_job_dead_letter_store()
    )
    dispatcher = queue_dispatcher or getattr(infra, "job_dispatcher", None)
    scheduler = queue_scheduler or getattr(infra, "job_scheduler", None)
    worker = queue_worker or getattr(infra, "job_worker", None)
    rate_limit_guard = queue_rate_limit_guard or getattr(infra, "queue_rate_limit_guard", None) or RateLimitGuard()
    backpressure_policy = queue_backpressure_policy or getattr(infra, "queue_backpressure_policy", None) or BackpressurePolicy()
    throttle_policy = queue_throttle_policy or getattr(infra, "queue_throttle_policy", None) or ThrottlePolicy()
    retry_policy = queue_retry_policy or getattr(infra, "queue_retry_policy", None) or JobRetryPolicy()

    if dispatcher is None:
        dispatcher = JobDispatcher(
            store=store,
            rate_limit_guard=rate_limit_guard,
            backpressure_policy=backpressure_policy,
        )
    if scheduler is None:
        scheduler = JobScheduler(
            store=store,
            throttle_policy=throttle_policy,
        )
    if worker is None:
        worker = JobWorker(
            worker_id=str(worker_id).strip() or "runtime-executor",
            store=store,
            scheduler=scheduler,
            runner=queue_runner or getattr(infra, "queue_runner", None) or _unsupported_queue_runner,
            retry_policy=retry_policy,
            dead_letter_store=dead_letter_store,
        )
    return RuntimeExecutorQueueSupport(
        store=store,
        dead_letter_store=dead_letter_store,
        dispatcher=dispatcher,
        scheduler=scheduler,
        worker=worker,
        rate_limit_guard=rate_limit_guard,
        backpressure_policy=backpressure_policy,
        throttle_policy=throttle_policy,
        retry_policy=retry_policy,
    )



def _unsupported_queue_runner(job: Any) -> Any:
    raise RuntimeError(f"runtime_queue_runner_not_configured:{getattr(job, 'job_type', 'unknown')}")



def build_executor_state(
    *,
    guard,
    handlers,
    event_log,
    policy_registry,
    reward_engine,
    learning_system,
    decision_core,
    runtime_infra,
    ledger,
    snapshot_store,
    outbox,
    payment_outbox,
    settings_gateway,
    messaging_policy_event_store,
    messaging_policy_read_service,
    delivery_state,
    telegram_outbound_queue,
    decision_archive,
    constitution,
    max_meta_depth,
    economic_layer,
):
    ports = RuntimeExecutorPorts(
        guard=guard,
        handlers=handlers,
        event_log=event_log,
        policy_registry=policy_registry,
        reward_engine=reward_engine,
        learning_system=learning_system,
        decision_core=decision_core,
        runtime_infra=runtime_infra,
    )
    if runtime_infra is not None:
        infra = runtime_infra
    else:
        infra = _build_runtime_infra(
            runtime_infra=None,
            ledger=ledger,
            snapshot_store=snapshot_store,
            outbox=outbox,
            payment_outbox=payment_outbox,
            settings_gateway=settings_gateway,
            messaging_policy_event_store=messaging_policy_event_store,
            messaging_policy_read_service=messaging_policy_read_service,
            delivery_state=delivery_state,
            telegram_outbound_queue=telegram_outbound_queue,
        )
    effects_bundle = build_executor_effects_bundle(
        event_log=event_log,
        policy_registry=policy_registry,
        infra=infra,
    )
    reliability = build_runtime_reliability(outbox=infra.effect_outbox, runtime_infra=runtime_infra or infra)
    return RuntimeExecutorState(
        ports=ports,
        infra=infra,
        effects=effects_bundle.effects,
        cap_token=effects_bundle.cap_token,
        archive=decision_archive,
        constitution=resolve_executor_constitution(constitution),
        economic_layer=resolve_executor_economic_layer(economic_layer),
        snapshot_store=infra.snapshot_archive,
        max_meta_depth=int(max_meta_depth),
        reliability=reliability,
    )


__all__ = [
    "CANON_RUNTIME_EXECUTOR_QUEUE_SUPPORT",
    "RuntimeExecutorQueueSupport",
    "RuntimeExecutorRecoverySupport",
    "build_runtime_infra",
    "build_executor_effects_bundle",
    "build_executor_queue_support",
    "build_executor_recovery_support",
    "build_executor_state",
    "resolve_executor_constitution",
    "resolve_executor_economic_layer",
    "emit_throttled_executor_warning",
    "build_executor_runtime_infra_from_runtime_infra",
]
