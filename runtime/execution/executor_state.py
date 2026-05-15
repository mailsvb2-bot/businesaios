from __future__ import annotations

"""Canonical execution assembly surface.

This module owns the assembled executor state plus the execution-specific
infra/ports/effects construction helpers. Older top-level ``runtime.executor_*``
modules remain as compatibility shims only.
"""

from dataclasses import dataclass, fields
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol

from governance.constitution import Constitution
from governance.economic_layer import EconomicAutonomyLayer

from runtime.execution.effects_factory import build_guarded_effects
from runtime.execution.executor_warnings import throttled_exec_warn
from runtime.firewall.import_guard import allow_internal_import
from runtime.runtime_infra import RuntimeInfra
from runtime.execution.reliability_runtime import build_runtime_reliability

CANON_RUNTIME_EXECUTION_ASSEMBLY = True


def _copy_runtime_infra_fields(*, source: RuntimeInfra | None, overrides: dict[str, Any] | None = None, exclude: tuple[str, ...] = ()) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    excluded = set(exclude)
    for field in fields(RuntimeInfra):
        if field.name in excluded:
            continue
        payload[field.name] = getattr(source, field.name, None) if source is not None else None
    if overrides:
        payload.update(overrides)
    return payload


class RuntimeExecutorPort(Protocol):
    def execute(self, env: Any) -> Any: ...


def _build_runtime_effects_wiring(*, http_transport, effect_router, telegram_outbound_queue, delivery_state):
    with allow_internal_import():
        http_transport_mod = import_module("runtime._internal.http_transport")
        build_http_transport = http_transport_mod.build_http_transport
        runtime_network_mode = http_transport_mod.runtime_network_mode
        effect_router_cls = import_module("runtime._internal.effect_router").EffectRouter

    transport = http_transport or build_http_transport(allow_network=(runtime_network_mode() == "enabled"))
    router = effect_router or effect_router_cls(transport=transport, outbound_queue=telegram_outbound_queue, delivery_state=delivery_state)
    if getattr(router, "transport", None) is None:
        router.transport = transport
    if getattr(router, "outbound_queue", None) is None:
        router.outbound_queue = telegram_outbound_queue
    if getattr(router, "delivery_state", None) is None:
        router.delivery_state = delivery_state
    return transport, router


@dataclass(frozen=True)
class RuntimeExecutorInfra(RuntimeInfra):
    reliability_base_dir: str | None = None
    delivery_state: Any = None
    telegram_outbound_queue: Any = None
    http_transport: Any = None
    effect_router: Any = None


@dataclass(frozen=True)
class RuntimeExecutorPorts:
    guard: Any
    handlers: Any
    event_log: Any
    policy_registry: Any
    reward_engine: Any = None
    learning_system: Any = None
    decision_core: Any = None
    runtime_infra: RuntimeExecutorInfra | None = None


@dataclass(frozen=True)
class RuntimeExecutorEffectsBundle:
    cap_token: Any
    effects: Any


@dataclass(frozen=True)
class RuntimeExecutorState:
    """Canonical assembled state for RuntimeExecutor.

    Keeps RuntimeExecutor focused on orchestration while construction of ports,
    infra, and effects remains explicit and testable on one path.
    """

    ports: RuntimeExecutorPorts
    infra: RuntimeExecutorInfra
    effects: Any
    cap_token: Any
    archive: Any
    constitution: Constitution
    economic_layer: EconomicAutonomyLayer | None
    snapshot_store: Any
    max_meta_depth: int
    reliability: Any = None


def build_runtime_executor_effects(
    *,
    event_log,
    policy_registry,
    delivery_state,
    ledger,
    payment_outbox,
    telegram_outbound_queue,
    settings_gateway,
    messaging_policy_event_store,
    messaging_policy_read_service,
    http_transport=None,
    effect_router=None,
) -> RuntimeExecutorEffectsBundle:
    """Build guarded effects exactly once for RuntimeExecutor."""

    with allow_internal_import():
        effects_cls = import_module("runtime._internal._effects_impl").Effects

    cap_token, effects = build_guarded_effects(
        effects_cls=effects_cls,
        event_log=event_log,
        policy_registry=policy_registry,
        delivery_state=delivery_state,
        ledger=ledger,
        payment_outbox=payment_outbox,
        telegram_outbound_queue=telegram_outbound_queue,
        settings_gateway=settings_gateway,
        messaging_policy_event_store=messaging_policy_event_store,
        messaging_policy_read_service=messaging_policy_read_service,
        http_transport=http_transport,
        effect_router=effect_router,
    )
    return RuntimeExecutorEffectsBundle(cap_token=cap_token, effects=effects)


def build_runtime_infra(
    *,
    runtime_infra: RuntimeExecutorInfra | None,
    ledger,
    snapshot_store,
    outbox,
    payment_outbox,
    settings_gateway,
    messaging_policy_event_store,
    messaging_policy_read_service,
    delivery_state,
    telegram_outbound_queue,
) -> RuntimeExecutorInfra:
    base = runtime_infra or RuntimeExecutorInfra(
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
    transport, router = _build_runtime_effects_wiring(
        http_transport=getattr(base, "http_transport", None),
        effect_router=getattr(base, "effect_router", None),
        telegram_outbound_queue=getattr(base, "telegram_outbound_queue", telegram_outbound_queue),
        delivery_state=getattr(base, "delivery_state", delivery_state),
    )
    resolved_ledger = getattr(base, "ledger", ledger)
    reliability_base_dir = getattr(base, "reliability_base_dir", None)
    if not reliability_base_dir:
        ledger_path = str(getattr(resolved_ledger, "_path", "") or "").strip()
        if ledger_path:
            reliability_base_dir = str(Path(ledger_path).parent / ".runtime")
    return RuntimeExecutorInfra(
        **_copy_runtime_infra_fields(
            source=base,
            exclude=("delivery_state", "telegram_outbound_queue", "http_transport", "effect_router"),
            overrides={
                "ledger": resolved_ledger,
                "snapshot_store": getattr(base, "snapshot_store", snapshot_store),
                "outbox": getattr(base, "outbox", outbox),
                "payment_outbox": getattr(base, "payment_outbox", payment_outbox),
                "settings_gateway": getattr(base, "settings_gateway", settings_gateway),
                "decision_archive": getattr(base, "decision_archive", None),
                "messaging_policy_event_store": getattr(base, "messaging_policy_event_store", messaging_policy_event_store),
                "messaging_policy_read_service": getattr(base, "messaging_policy_read_service", messaging_policy_read_service),
            },
        ),
        reliability_base_dir=reliability_base_dir,
        delivery_state=getattr(base, "delivery_state", delivery_state),
        telegram_outbound_queue=getattr(base, "telegram_outbound_queue", telegram_outbound_queue),
        http_transport=transport,
        effect_router=router,
    )



def build_executor_runtime_infra_from_runtime_infra(*, runtime_infra, delivery_state, telegram_outbound_queue):
    return build_runtime_infra(
        runtime_infra=RuntimeExecutorInfra(
            **_copy_runtime_infra_fields(source=runtime_infra, exclude=("delivery_state", "telegram_outbound_queue", "http_transport", "effect_router")),
            delivery_state=delivery_state,
            telegram_outbound_queue=telegram_outbound_queue,
            http_transport=getattr(runtime_infra, "http_transport", None),
            effect_router=getattr(runtime_infra, "effect_router", None),
        ),
        ledger=getattr(runtime_infra, "ledger", None),
        snapshot_store=getattr(runtime_infra, "snapshot_store", None),
        outbox=getattr(runtime_infra, "outbox", None),
        payment_outbox=getattr(runtime_infra, "payment_outbox", None),
        settings_gateway=getattr(runtime_infra, "settings_gateway", None),
        messaging_policy_event_store=getattr(runtime_infra, "messaging_policy_event_store", None),
        messaging_policy_read_service=getattr(runtime_infra, "messaging_policy_read_service", None),
        delivery_state=delivery_state,
        telegram_outbound_queue=telegram_outbound_queue,
    )


def build_executor_effects_bundle(*, event_log, policy_registry, infra: RuntimeExecutorInfra):
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



def build_executor_state(
    *,
    guard,
    handlers,
    event_log,
    policy_registry,
    reward_engine,
    learning_system,
    decision_core,
    runtime_infra: RuntimeExecutorInfra | None,
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
    constitution: Constitution | None,
    max_meta_depth: int,
    economic_layer: EconomicAutonomyLayer | None,
) -> RuntimeExecutorState:
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
    resolved_ledger = ledger or getattr(guard, "_ledger", None)
    resolved_snapshot_store = snapshot_store or getattr(runtime_infra, "snapshot_store", None)
    infra = build_runtime_infra(
        runtime_infra=runtime_infra,
        ledger=resolved_ledger,
        snapshot_store=resolved_snapshot_store,
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


def resolve_executor_constitution(constitution: Constitution | None) -> Constitution:
    return constitution or Constitution()


def resolve_executor_economic_layer(
    economic_layer: EconomicAutonomyLayer | None,
) -> EconomicAutonomyLayer | None:
    return economic_layer


def emit_throttled_executor_warning(*, logger, key: str, error: Exception) -> None:
    throttled_exec_warn(logger=logger, key=key, e=error)


__all__ = [
    "CANON_RUNTIME_EXECUTION_ASSEMBLY",
    "RuntimeExecutorPort",
    "RuntimeExecutorInfra",
    "RuntimeExecutorPorts",
    "RuntimeExecutorEffectsBundle",
    "RuntimeExecutorState",
    "build_runtime_executor_effects",
    "build_runtime_infra",
    "build_executor_runtime_infra_from_runtime_infra",
    "build_executor_effects_bundle",
    "build_executor_state",
    "resolve_executor_constitution",
    "resolve_executor_economic_layer",
    "emit_throttled_executor_warning",
]
