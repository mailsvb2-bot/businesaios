from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, TYPE_CHECKING

from config.env_flags import env_bool
from entrypoints.api.openapi_tags import OPENAPI_TAGS

if TYPE_CHECKING:  # pragma: no cover
    from fastapi import FastAPI
    from adapters.api.fastapi.dependencies import FastAPIDependencyContainer
else:
    FastAPI = Any  # type: ignore[misc,assignment]
    FastAPIDependencyContainer = Any  # type: ignore[misc,assignment]

API_TITLE = 'BusinesAIOS API'
API_VERSION = '1.0.0'
CANON_FASTAPI_APP_FACTORY = True


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_version(default: str = API_VERSION) -> str:
    try:
        text = (_project_root() / 'VERSION').read_text(encoding='utf-8').strip()
    except OSError:
        return default
    return text or default


def _validate_inputs(*, application_service: object, dependency_container: object | None) -> None:
    if application_service is None:
        raise ValueError('application_service is required')
    if dependency_container is None:
        return
    boot_result = getattr(dependency_container, 'boot_result', None)
    if boot_result is None:
        raise ValueError('dependency_container.boot_result is required when dependency_container is provided')
    boot_service = getattr(boot_result, 'decision_application', None)
    if boot_service is not None and boot_service is not application_service:
        raise ValueError('dependency_container.boot_result.decision_application must match application_service')



class _FailsClosedApplicationService:
    """Safe fail-closed default used only when the API is instantiated without a wired runtime."""

    CANON_API_FAILS_CLOSED_DEFAULT_SERVICE = True

    def startup_audit_events(self) -> tuple[dict[str, str], ...]:
        return ({"status": "blocked", "reason": "runtime_application_service_not_wired"},)

    def execute_action(self, action: object, **_: object) -> dict[str, object]:
        action_type = getattr(action, "action_type", None) or getattr(action, "type", None)
        if not action_type and isinstance(action, dict):
            action_type = action.get("action_type") or action.get("type")
        return {
            "status": "blocked",
            "action_type": str(action_type or ""),
            "reason": "runtime_application_service_not_wired",
            "details": {},
            "capability_view": {},
        }


def create_app(*, application_service: object | None = None, dependency_container: object | None = None) -> FastAPI:
    """Backward-compatible public factory with safe default runtime.

    With an explicit runtime service it delegates to the canonical full factory.
    Without one it creates a minimal fail-closed API app for smoke tests and docs.
    """

    if application_service is not None or dependency_container is not None:
        return create_fastapi_app(
            application_service=application_service or _FailsClosedApplicationService(),
            dependency_container=dependency_container,
        )

    class _FailClosedAsgiApp:
        """Tiny ASGI app for default fail-closed smoke surface.

        It intentionally avoids importing the full FastAPI/control-plane graph.
        """

        routes = ()

        def __init__(self) -> None:
            self.state = type("State", (), {})()
            self.state.application_service = _FailsClosedApplicationService()
            self.state.dependency_container = None

        async def __call__(self, scope: dict[str, object], receive: object, send: object) -> None:
            if scope.get("type") != "http":
                return
            method = str(scope.get("method") or "GET").upper()
            path = str(scope.get("path") or "/")
            if method == "POST" and path == "/actions/execute":
                body = b""
                more = True
                while more:
                    message = await receive()  # type: ignore[misc]
                    body += message.get("body", b"")
                    more = bool(message.get("more_body", False))
                try:
                    payload = json.loads(body.decode("utf-8") or "{}")
                except Exception:
                    payload = {}
                action_type = str(payload.get("action_type") or "")
                response = {
                    "status": "blocked",
                    "action_type": action_type,
                    "reason": "runtime_application_service_not_wired",
                    "details": {},
                    "capability_view": {},
                }
                status = 200
            elif method == "GET" and path == "/health":
                response = {"status": "ok", "mode": "fails_closed"}
                status = 200
            elif method == "GET" and path == "/readyz":
                response = {"status": "blocked", "reason": "runtime_application_service_not_wired"}
                status = 200
            else:
                response = {"detail": "not_found"}
                status = 404
            data = json.dumps(response).encode("utf-8")
            await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(data)).encode())]})  # type: ignore[misc]
            await send({"type": "http.response.body", "body": data})  # type: ignore[misc]

    return _FailClosedAsgiApp()


def create_fastapi_app(*, application_service: object, dependency_container: object | None = None) -> FastAPI:
    try:
        from fastapi import FastAPI as _FastAPI
    except ModuleNotFoundError as exc:
        raise RuntimeError('FastAPI is required to create the API app. Install project requirements first.') from exc
    from adapters.api.fastapi.exception_handlers import register_exception_handlers
    from adapters.api.fastapi.router_adapter import create_api_router
    from adapters.api.fastapi.openapi_security import attach_security_schema

    _validate_inputs(application_service=application_service, dependency_container=dependency_container)
    docs_enabled = env_bool('API_DOCS_ENABLED', default=True)

    @asynccontextmanager
    async def _lifespan(_: object):
        try:
            yield
        finally:
            boot_result = getattr(dependency_container, 'boot_result', None) if dependency_container is not None else None
            runtime_infra = getattr(boot_result, 'runtime_infra', None) if boot_result is not None else None
            shutdown = getattr(runtime_infra, 'shutdown', None)
            if callable(shutdown):
                shutdown()

    app = _FastAPI(
        title=API_TITLE,
        version=_read_version(),
        openapi_tags=OPENAPI_TAGS,
        docs_url='/docs' if docs_enabled else None,
        redoc_url='/redoc' if docs_enabled else None,
        openapi_url='/openapi.json' if docs_enabled else None,
        lifespan=_lifespan if dependency_container is not None else None,
    )
    app.state.application_service = application_service
    app.state.dependency_container = dependency_container
    register_exception_handlers(app)
    app.include_router(
        create_api_router(
            application_service=application_service,
            dependency_container=dependency_container,
        )
    )
    attach_security_schema(app)
    return app
