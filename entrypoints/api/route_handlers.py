from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from entrypoints.api.action_models import ExecuteActionRequest, ExecuteActionResponse
from entrypoints.api.execute_action_handler import ExecuteActionHandler, build_execute_action_handler
from entrypoints.api.health_models import HealthResponse
from entrypoints.api.request_context import RequestContext


CANON_API_ROUTE_HANDLERS_FINAL_OWNER = True
CANON_API_ROUTE_HANDLERS_DEFAULT_HANDLER_OWNER = True


class ExecuteActionPort(Protocol):
    def handle(
        self,
        request: ExecuteActionRequest,
        *,
        request_context: RequestContext | None = None,
        idempotency_key: str | None = None,
        action_id: str | None = None,
    ) -> ExecuteActionResponse: ...


def build_default_route_execute_action_handler(*, application_service: object) -> ExecuteActionHandler:
    return build_execute_action_handler(application_service=application_service)


def build_route_handlers(
    *,
    application_service: object,
    execute_action_handler: ExecuteActionHandler | None = None,
    execute_action_port: ExecuteActionPort | None = None,
) -> "RouteHandlers":
    return RouteHandlers(
        application_service=application_service,
        execute_action_handler=execute_action_handler,
        execute_action_port=execute_action_port,
    )


@dataclass(frozen=True)
class RouteHandlers:
    application_service: object
    execute_action_handler: ExecuteActionHandler | None = field(default=None)
    execute_action_port: ExecuteActionPort | None = field(default=None)

    def execute_action(
        self,
        request: ExecuteActionRequest,
        *,
        request_context: RequestContext | None = None,
        idempotency_key: str | None = None,
        action_id: str | None = None,
    ) -> ExecuteActionResponse:
        port = self.execute_action_port
        if port is not None:
            return port.handle(
                request,
                request_context=request_context,
                idempotency_key=idempotency_key,
                action_id=action_id,
            )
        handler = self.execute_action_handler or build_default_route_execute_action_handler(
            application_service=self.application_service
        )
        return handler.handle(
            request,
            request_context=request_context,
            idempotency_key=idempotency_key,
            action_id=action_id,
        )

    def health(self) -> HealthResponse:
        events = self.application_service.startup_audit_events()
        return HealthResponse(
            status="ok",
            startup_audit_events=list(events),
        )


__all__ = [
    "CANON_API_ROUTE_HANDLERS_DEFAULT_HANDLER_OWNER",
    "CANON_API_ROUTE_HANDLERS_FINAL_OWNER",
    "ExecuteActionPort",
    "RouteHandlers",
    "build_default_route_execute_action_handler",
    "build_route_handlers",
]
