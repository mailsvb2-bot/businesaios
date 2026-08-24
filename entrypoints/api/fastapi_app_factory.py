from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from config.env_flags import env_bool, env_csv, env_str
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
DEFAULT_API_CORS_ALLOWED_ORIGINS = ('https://app.businessaios.ru',)
_FAIL_CLOSED_REASON = 'runtime_application_service_not_wired'


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_version(default: str = API_VERSION) -> str:
    try:
        text = (_project_root() / 'VERSION').read_text(encoding='utf-8').strip()
    except OSError:
        return default
    return text or default


def _is_production_env() -> bool:
    return (env_str('APP_ENV', '').strip().lower() in {'prod', 'production'}
            or env_str('ENV', '').strip().lower() in {'prod', 'production'})


def _api_docs_enabled() -> bool:
    return env_bool('API_DOCS_ENABLED', default=not _is_production_env())


def _api_cors_allowed_origins() -> tuple[str, ...]:
    allowed: list[str] = []
    for raw in env_csv('API_CORS_ALLOWED_ORIGINS', '') or DEFAULT_API_CORS_ALLOWED_ORIGINS:
        origin = str(raw or '').strip().rstrip('/')
        parsed = urlsplit(origin)
        if not origin or '*' in origin:
            raise ValueError('API_CORS_ALLOWED_ORIGINS must contain exact origins and must not use wildcards')
        invalid = (parsed.scheme not in {'http', 'https'} or not parsed.netloc
                   or parsed.username is not None or parsed.password is not None or parsed.path not in {'', '/'}
                   or bool(parsed.query or parsed.fragment))
        if invalid:
            raise ValueError(f'invalid CORS origin: {raw!r}')
        if _is_production_env() and parsed.scheme != 'https':
            raise ValueError('production CORS origins must use https')
        allowed.append(f'{parsed.scheme.lower()}://{parsed.netloc.lower()}')
    return tuple(dict.fromkeys(allowed))


def _configure_browser_cors(app: object) -> None:
    from starlette.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(_api_cors_allowed_origins()),
        allow_credentials=True,
        allow_methods=['GET', 'POST', 'OPTIONS'],
        allow_headers=['Content-Type', 'X-API-Key'],
    )


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
        return ({"status": "blocked", "reason": _FAIL_CLOSED_REASON},)

    def execute_action(self, action: object, **_: object) -> dict[str, object]:
        if isinstance(action, dict):
            action_type = action.get("action_type") or action.get("type")
        else:
            action_type = getattr(action, "action_type", None) or getattr(action, "type", None)
        return {
            "status": "blocked", "action_type": str(action_type or ""), "reason": _FAIL_CLOSED_REASON,
            "details": {}, "capability_view": {},
        }


def _fail_closed_status(*, surface: str) -> dict[str, object]:
    details = {
        "health": {"status": "alive", "process_alive": True, "ready": False},
        "livez": {"status": "alive", "process_alive": True},
        "startupz": {"status": "blocked", "startup_complete": False},
        "storagez": {"status": "blocked", "storage_ready": False},
        "executionz": {"status": "blocked", "execution_ready": False, "effects_enabled": False},
    }.get(surface, {"status": "blocked", "ready": False})
    return {"surface": surface, "mode": "fails_closed", "runtime_wired": False,
            "reason": _FAIL_CLOSED_REASON, **details}


def create_app(*, application_service: object | None = None, dependency_container: object | None = None) -> FastAPI:
    """Backward-compatible public factory with safe default runtime."""
    if application_service is not None or dependency_container is not None:
        return create_fastapi_app(
            application_service=application_service or _FailsClosedApplicationService(),
            dependency_container=dependency_container,
        )

    class _FailClosedAsgiApp:
        """Tiny ASGI fail-closed smoke surface without the full control-plane graph."""
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
                body, more = b"", True
                while more:
                    message = await receive()  # type: ignore[misc]
                    body += message.get("body", b"")
                    more = bool(message.get("more_body", False))
                try:
                    payload = json.loads(body.decode("utf-8") or "{}")
                except Exception:
                    payload = {}
                response = {"status": "blocked", "action_type": str(payload.get("action_type") or ""),
                            "reason": _FAIL_CLOSED_REASON, "details": {}, "capability_view": {}}
                status = 200
            elif method == "GET" and path in {"/health", "/readyz", "/livez", "/startupz", "/storagez", "/executionz"}:
                response, status = _fail_closed_status(surface=path.removeprefix("/")), 200
            else:
                response, status = {"detail": "not_found"}, 404
            data = json.dumps(response).encode("utf-8")
            headers = [(b"content-type", b"application/json"), (b"content-length", str(len(data)).encode())]
            await send({"type": "http.response.start", "status": status, "headers": headers})  # type: ignore[misc]
            await send({"type": "http.response.body", "body": data})  # type: ignore[misc]

    return _FailClosedAsgiApp()


def create_fastapi_app(*, application_service: object, dependency_container: object | None = None) -> FastAPI:
    try:
        from fastapi import FastAPI as _FastAPI
    except ModuleNotFoundError as exc:
        raise RuntimeError('FastAPI is required to create the API app. Install project requirements first.') from exc
    from adapters.api.fastapi.exception_handlers import register_exception_handlers
    from adapters.api.fastapi.openapi_security import attach_security_schema
    from adapters.api.fastapi.router_adapter import create_api_router

    _validate_inputs(application_service=application_service, dependency_container=dependency_container)
    docs_enabled = _api_docs_enabled()

    @asynccontextmanager
    async def _lifespan(_: object):
        try:
            yield
        finally:
            boot_result = (getattr(dependency_container, 'boot_result', None)
                           if dependency_container is not None else None)
            runtime_infra = getattr(boot_result, 'runtime_infra', None) if boot_result is not None else None
            shutdown = getattr(runtime_infra, 'shutdown', None)
            if callable(shutdown):
                shutdown()

    app = _FastAPI(title=API_TITLE, version=_read_version(), openapi_tags=OPENAPI_TAGS,
                   docs_url='/docs' if docs_enabled else None, redoc_url='/redoc' if docs_enabled else None,
                   openapi_url='/openapi.json' if docs_enabled else None,
                   lifespan=_lifespan if dependency_container is not None else None)
    _configure_browser_cors(app)
    app.state.application_service = application_service
    app.state.dependency_container = dependency_container
    register_exception_handlers(app)
    app.include_router(create_api_router(
        application_service=application_service,
        dependency_container=dependency_container,
    ))
    attach_security_schema(app)
    return app
