from fastapi import APIRouter, FastAPI

from scripts.ci.step_boot_smoke import _probe_http_app, _route_paths


def test_boot_smoke_inventory_includes_nested_hidden_routes():
    app = FastAPI()
    outer = APIRouter()
    inner = APIRouter()

    @inner.get("/readyz", include_in_schema=False)
    def ready():
        return {"status": "ok"}

    outer.include_router(inner, prefix="/nested")
    app.include_router(outer, prefix="/api")
    assert "/api/nested/readyz" in _route_paths(app)
    assert "/readyz" not in _route_paths(app)
    assert "/api/nested/readyz" not in app.openapi()["paths"]


def test_boot_smoke_missing_routes_still_fail_http_probe():
    app = FastAPI()
    router = APIRouter()

    @router.get("/readyz")
    def ready():
        return {"status": "ok"}

    app.include_router(router)
    assert "/readyz" in _route_paths(app)
    assert "/storagez" not in _route_paths(app)
    _, violations = _probe_http_app(app)
    assert set(violations) == {
        "http_probe_failed:/storagez:404",
        "http_probe_failed:/executionz:404",
    }
