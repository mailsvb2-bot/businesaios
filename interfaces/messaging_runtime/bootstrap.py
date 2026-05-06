from __future__ import annotations

from .channel_loader import load_bindings
from .registry import ChannelRegistry
from .config import load_runtime_config
from .defaults import default_compose_view
from .outbound.ack_reconciliation import ProviderAckReconciliationService
from .outbound.backpressure import QueueBackpressureGuard
from .outbound.delivery_dispatcher import DeliveryDispatcher
from .outbound.provider_ack_store import ProviderAckStore
from .outbound.queue_service import DurableOutboundQueueService
from .outbound.retry_policy import DeliveryRetryPolicy
from .outbound.stores import DeadLetterStore, DeliveryAttemptStore, DurableOutboundQueueStore
from .pipeline import MessagingRuntimePipeline
from .runner import ChannelRuntimeRunner
from .state.checkpoints import ConversationCheckpointService
from .state.guards import InboundIdempotencyGuard
from .state.stores import ConversationCheckpointStore, IdempotencyLockStore, InboxStateStore
from .telemetry import AuditTrailStore, InMemoryTelemetrySink, RuntimeAnomalyHooks, RuntimeTelemetryFacade
from .view_resolver import ChannelAwareViewResolver
from .worldstate_builder import CanonicalWorldStateBuilder


class MultichannelRuntimeApp:
    def __init__(self, *, config, registry, runners, queue_service, telemetry_sink, audit_trail, anomaly_hooks, dispatcher, attempt_store, dead_letter_store, checkpoint_store, ack_store, ack_reconciliation) -> None:
        self.config = config
        self.registry = registry
        self.runners = runners
        self.queue_service = queue_service
        self.telemetry = telemetry_sink
        self.audit_trail = audit_trail
        self.anomaly_hooks = anomaly_hooks
        self.dispatcher = dispatcher
        self.attempt_store = attempt_store
        self.dead_letter_store = dead_letter_store
        self.checkpoint_store = checkpoint_store
        self.ack_store = ack_store
        self.ack_reconciliation = ack_reconciliation

    def accept_inbound(self, channel: str, raw: dict):
        return self.runners[channel].accept_inbound(raw)


def build_multichannel_runtime_app(*, build_world_state, raw_config: dict | None = None, compose_view=None, senders: dict[str, object] | None = None) -> MultichannelRuntimeApp:
    config = load_runtime_config(raw_config)
    enabled_channels = tuple(sorted(name for name, item in config.channels.items() if item.enabled))
    if not enabled_channels:
        raise RuntimeError("no enabled channels configured")

    queue_limit = int(config.defaults.get("queue_limit", min(config.channels[ch].backpressure_limit for ch in enabled_channels)))
    max_attempts = int(config.defaults.get("max_attempts", max(config.channels[ch].retry_max_attempts for ch in enabled_channels)))

    sink = InMemoryTelemetrySink()
    audit_trail = AuditTrailStore()
    anomaly_hooks = RuntimeAnomalyHooks()
    telemetry = RuntimeTelemetryFacade(sink=sink, audit_trail=audit_trail, anomaly_hooks=anomaly_hooks)

    queue_service = DurableOutboundQueueService(
        store=DurableOutboundQueueStore(),
        guard=QueueBackpressureGuard(max_size=queue_limit),
    )
    registry = ChannelRegistry()
    bindings = load_bindings(enabled_channels=enabled_channels, senders=senders)
    for binding in bindings:
        registry.register(binding)

    checkpoint_store = ConversationCheckpointStore()
    pipeline = MessagingRuntimePipeline(
        worldstate_builder=CanonicalWorldStateBuilder(build_world_state),
        compose_view=compose_view or default_compose_view,
        view_resolver=ChannelAwareViewResolver(),
        outbound_queue=queue_service,
        inbound_guard=InboundIdempotencyGuard(
            inbox_state_store=InboxStateStore(),
            lock_store=IdempotencyLockStore(),
        ),
        checkpoint_service=ConversationCheckpointService(store=checkpoint_store),
        telemetry=telemetry,
    )

    runners = {binding.channel: ChannelRuntimeRunner(binding=binding, pipeline=pipeline) for binding in bindings}
    attempt_store = DeliveryAttemptStore()
    dead_letter_store = DeadLetterStore()
    dispatcher = DeliveryDispatcher(
        registry=registry,
        queue_service=queue_service,
        telemetry=telemetry,
        retry_policy=DeliveryRetryPolicy(max_attempts=max_attempts),
        attempt_store=attempt_store,
        dead_letter_store=dead_letter_store,
    )
    ack_store = ProviderAckStore()
    ack_reconciliation = ProviderAckReconciliationService(
        ack_store=ack_store,
        attempt_store=attempt_store,
        telemetry=telemetry,
    )

    return MultichannelRuntimeApp(
        config=config,
        registry=registry,
        runners=runners,
        queue_service=queue_service,
        telemetry_sink=sink,
        audit_trail=audit_trail,
        anomaly_hooks=anomaly_hooks,
        dispatcher=dispatcher,
        attempt_store=attempt_store,
        dead_letter_store=dead_letter_store,
        checkpoint_store=checkpoint_store,
        ack_store=ack_store,
        ack_reconciliation=ack_reconciliation,
    )
