from __future__ import annotations

import importlib
from pathlib import Path


def test_runtime_api_bundle_is_single_owner_surface() -> None:
    text = Path('entrypoints/api/runtime_api_bundle.py').read_text(encoding='utf-8')
    assert 'build_runtime_api_bundle(' in text
    assert 'build_runtime_api_adapter(' in text
    assert 'build_api_handler_bundle(' in text
    assert hasattr(importlib.import_module('interfaces.api.runtime_api_bundle'), 'build_runtime_api_bundle')


def test_fastapi_router_uses_runtime_api_bundle_owner() -> None:
    text = Path('adapters/api/fastapi/router_adapter.py').read_text(encoding='utf-8')
    assert 'build_runtime_api_bundle(' in text
    assert 'build_api_handler_bundle(' not in text
    assert hasattr(importlib.import_module('interfaces.api.fastapi_router_adapter'), 'create_api_router')


def test_route_handlers_use_shared_default_handler_builder() -> None:
    text = Path('entrypoints/api/route_handlers.py').read_text(encoding='utf-8')
    assert 'CANON_API_ROUTE_HANDLERS_DEFAULT_HANDLER_OWNER = True' in text
    assert 'build_default_route_execute_action_handler(' in text
    assert 'ExecuteActionHandler(application_service=self.application_service)' not in text
    assert hasattr(importlib.import_module('interfaces.api.route_handlers'), 'RouteHandlers')


def test_ads_autopilot_flow_uses_shared_decision_execution_owner() -> None:
    text = Path('runtime/handlers/ads_autopilot_flow.py').read_text(encoding='utf-8')
    assert 'CANON_ADS_AUTOPILOT_EXECUTION_SHARED_OWNER = True' in text
    assert 'validate_and_run_decision_command(' in text
    assert 'command.validate()' not in text
    assert 'service.run(command)' not in text
