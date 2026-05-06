from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


def test_boot_runtime_integration_and_startup_pipeline_have_bootstrap_final_owners() -> None:
    runtime_integration = _read("bootstrap/runtime_integration.py")
    startup_pipeline = _read("bootstrap/startup_pipeline.py")
    boot_runtime_integration = _read("boot/runtime_integration.py")
    boot_root = _read("boot/__init__.py")

    assert "CANON_RUNTIME_INTEGRATION_FINAL_OWNER = True" in runtime_integration
    assert "CANON_STARTUP_PIPELINE_FINAL_OWNER = True" in startup_pipeline
    assert "Final owner: bootstrap.runtime_integration" in boot_runtime_integration
    assert "\"startup_pipeline\": \"bootstrap.startup_pipeline\"" in boot_root


def test_api_models_and_runtime_adapter_have_final_owner_surfaces() -> None:
    action_models = _read("entrypoints/api/action_models.py")
    headless_models = _read("entrypoints/api/headless_models.py")
    health_models = _read("entrypoints/api/health_models.py")
    runtime_adapter = _read("adapters/api/runtime_api_adapter.py")

    assert "class ExecuteActionRequest(BaseModel)" in action_models
    assert "class ExecuteGoalRequest(BaseModel)" in headless_models
    assert "class HealthResponse(BaseModel)" in health_models
    assert "class RuntimeApiAdapter:" in runtime_adapter

    assert hasattr(importlib.import_module("interfaces.api.action_models"), "ExecuteActionRequest")
    assert hasattr(importlib.import_module("interfaces.api.headless_models"), "ExecuteGoalRequest")
    assert hasattr(importlib.import_module("interfaces.api.health_models"), "HealthResponse")
    assert hasattr(importlib.import_module("interfaces.api.runtime_api_adapter"), "RuntimeApiAdapter")


def test_entrypoint_owners_use_transferred_model_and_adapter_surfaces() -> None:
    route_handlers = _read("entrypoints/api/route_handlers.py")
    health_handler = _read("entrypoints/api/health_handler.py")
    runtime_bundle = _read("entrypoints/api/runtime_api_bundle.py")

    assert "from entrypoints.api.action_models import ExecuteActionRequest, ExecuteActionResponse" in route_handlers
    assert "from entrypoints.api.health_models import HealthResponse" in route_handlers
    assert "from entrypoints.api.health_models import HealthCheckView, HealthResponse" in health_handler
    assert "from adapters.api.runtime_api_adapter import RuntimeApiAdapter, build_runtime_api_adapter" in runtime_bundle
