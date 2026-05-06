from __future__ import annotations

import importlib
from pathlib import Path


def _text(relative: str) -> str:
    return Path(relative).read_text(encoding='utf-8')


def test_route_handlers_and_runtime_api_adapter_expose_single_owner_builders() -> None:
    route_handlers = _text('entrypoints/api/route_handlers.py')
    runtime_adapter = _text('adapters/api/runtime_api_adapter.py')
    assert 'def build_route_handlers(' in route_handlers
    assert 'CANON_API_RUNTIME_ADAPTER_SINGLE_OWNER = True' in runtime_adapter
    assert 'def build_runtime_api_adapter(' in runtime_adapter
    assert hasattr(importlib.import_module('interfaces.api.route_handlers'), 'build_route_handlers')
    assert hasattr(importlib.import_module('interfaces.api.runtime_api_adapter'), 'build_runtime_api_adapter')


def test_fastapi_router_uses_runtime_api_bundle_owner() -> None:
    text = _text('adapters/api/fastapi/router_adapter.py')
    assert 'build_runtime_api_bundle(' in text
    assert 'handlers = handler_bundle.route_handlers' in text
    assert 'RouteHandlers(application_service=application_service, execute_action_port=execute_action_port)' not in text


def test_fastapi_router_no_longer_builds_api_handler_bundle_directly() -> None:
    text = _text('adapters/api/fastapi/router_adapter.py')
    assert 'build_api_handler_bundle(' not in text
    assert 'handler_bundle = build_api_handler_bundle(' not in text
    assert 'headless_handlers = handler_bundle.headless_handlers' in text
    assert 'business_memory_handlers = handler_bundle.business_memory_handlers' in text
