from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_execute_action_stack_uses_shared_bundle_owner_for_wrappers() -> None:
    api_stack = _text('entrypoints/api/execute_action_api_stack.py')
    stack_bundle = _text('entrypoints/api/execute_action_stack_bundle.py')
    assert 'build_execute_action_stack_bundle(' in api_stack
    assert 'build_execute_action_handler(' not in api_stack
    assert 'build_execute_action_guarded_handler(' not in api_stack
    assert 'build_execute_action_control_plane(' not in api_stack
    assert 'build_execute_action_handler(' in stack_bundle
    assert 'build_execute_action_guarded_handler(' in stack_bundle
    assert 'build_execute_action_control_plane(' in stack_bundle
    assert hasattr(importlib.import_module('interfaces.api.execute_action_api_stack'), 'build_execute_action_stack_bundle')
    assert hasattr(importlib.import_module('interfaces.api.execute_action_stack_bundle'), 'build_execute_action_stack_bundle')


def test_api_handler_bundle_reuses_execute_action_port_provider_owner() -> None:
    text = _text('entrypoints/api/api_handler_bundle.py')
    assert 'build_execute_action_port_provider(' in text
    assert 'execute_action_port_provider.build_port()' in text
    assert 'execute_action_port_provider=execute_action_port_provider' in text
    assert hasattr(importlib.import_module('interfaces.api.api_handler_bundle'), 'build_api_handler_bundle')


def test_runtime_decision_execution_service_exposes_single_owner_builder() -> None:
    text = _text('runtime/execution/decision_execution_service.py')
    assert 'CANON_RUNTIME_DECISION_EXECUTION_SERVICE_OWNER = True' in text
    assert 'def build_decision_execution_service(' in text


def test_ads_autopilot_flow_uses_shared_decision_execution_service_builder() -> None:
    text = _text('runtime/handlers/ads_autopilot_flow.py')
    assert 'CANON_ADS_AUTOPILOT_EXECUTION_THIN_BOUNDARY = True' in text
    assert 'build_decision_execution_service(' in text
    assert 'def build_ads_autopilot_execution_service(' in text
