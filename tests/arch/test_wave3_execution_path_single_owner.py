from __future__ import annotations

import importlib
from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_execution_path_lock_is_single_owner_surface() -> None:
    text = _read('runtime/execution/execution_path_lock.py')
    assert 'CANON_EXECUTION_PATH_LOCK_SINGLE_OWNER = True' in text
    assert "'decision'," in text
    assert "'envelope'," in text
    assert "'executor_entrypoint'," in text
    assert "'execution_gateway'," in text
    assert 'def validate_and_lock_execution_path(' in text
    assert 'def execute_locked_decision(' in text


def test_decision_execution_service_uses_execution_path_lock() -> None:
    text = _read('runtime/execution/decision_execution_service.py')
    assert 'validate_and_lock_execution_path(' in text
    assert 'execute_locked_decision(' in text
    assert '.to_signed_envelope(' not in text


def test_headless_gateway_uses_execution_path_lock() -> None:
    text = _read('application/headless/execution_gateway.py')
    assert 'build_execution_path_lock_spec(' in text or 'validate_headless_executor(' in text


def test_runtime_and_api_bundles_share_execution_path_lock_owner() -> None:
    runtime_bundle = _read('entrypoints/api/runtime_api_bundle.py')
    stack_bundle = _read('entrypoints/api/execute_action_stack_bundle.py')
    entrypoint_bundle = _read('runtime/execution/executor_entrypoint_bundle.py')
    assert 'build_execution_path_lock_spec(' in runtime_bundle
    assert 'build_execution_path_lock_spec(' in stack_bundle
    assert 'build_execution_path_lock_spec(' in entrypoint_bundle
    assert hasattr(importlib.import_module('interfaces.api.runtime_api_bundle'), 'build_runtime_api_bundle')
    assert hasattr(importlib.import_module('interfaces.api.execute_action_stack_bundle'), 'build_execute_action_stack_bundle')
