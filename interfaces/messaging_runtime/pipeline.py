from __future__ import annotations

from .routing import build_route_command


class MessagingRuntimePipeline:
    def __init__(self, *, worldstate_builder, compose_view, view_resolver, outbound_queue, inbound_guard, checkpoint_service, telemetry) -> None:
        self._worldstate_builder = worldstate_builder
        self._compose_view = compose_view
        self._view_resolver = view_resolver
        self._outbound_queue = outbound_queue
        self._inbound_guard = inbound_guard
        self._checkpoint_service = checkpoint_service
        self._telemetry = telemetry

    def process(self, message):
        self._inbound_guard.enter(message.message_id)
        try:
            route = build_route_command(message)
            self._telemetry.emit(
                event_name="route_built",
                correlation_id=message.correlation_id,
                channel=message.channel,
                severity="info",
                component="pipeline.routing",
                payload={"route_key": route.route_key},
            )
            world_state = self._worldstate_builder.build(message)
            self._telemetry.emit(
                event_name="worldstate_built",
                correlation_id=message.correlation_id,
                channel=message.channel,
                severity="info",
                component="pipeline.worldstate",
                payload={"user_id": message.user_id},
            )
            view = self._compose_view(world_state, message)
            outbound = self._view_resolver.resolve(view)
            self._outbound_queue.enqueue(outbound)
            self._checkpoint_service.save_after_pipeline(message=message, outbound=outbound)
            self._inbound_guard.commit(message.message_id)
            self._telemetry.emit(
                event_name="outbound_enqueued",
                correlation_id=message.correlation_id,
                channel=message.channel,
                severity="info",
                component="pipeline.outbound_queue",
                payload={"queue_size": self._outbound_queue.size(), "dedupe_key": outbound.dedupe_key},
            )
            return outbound
        except Exception:
            self._inbound_guard.abort(message.message_id)
            raise
