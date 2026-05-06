from __future__ import annotations

import importlib
from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_execute_action_stack_bundle_is_single_owner() -> None:
    text = _read('entrypoints/api/execute_action_stack_bundle.py')
    assert 'build_execute_action_stack_bundle(' in text
    assert 'build_execute_action_handler(' in text
    assert 'build_execute_action_guarded_handler(' in text
    assert 'build_execute_action_control_plane(' in text
    assert hasattr(importlib.import_module('interfaces.api.execute_action_stack_bundle'), 'build_execute_action_stack_bundle')


def test_execute_action_api_stack_uses_bundle_owner() -> None:
    text = _read('entrypoints/api/execute_action_api_stack.py')
    assert 'build_execute_action_stack_bundle(' in text
    assert 'build_execute_action_handler(' not in text
    assert 'build_execute_action_guarded_handler(' not in text
    assert 'build_execute_action_control_plane(' not in text
    assert hasattr(importlib.import_module('interfaces.api.execute_action_api_stack'), 'build_execute_action_stack_bundle')


def test_executor_entrypoint_bundle_is_single_owner() -> None:
    text = _read('runtime/execution/executor_entrypoint_bundle.py')
    assert 'CANON_RUNTIME_EXECUTOR_ENTRYPOINT_BUNDLE_OWNER = True' in text
    assert 'build_executor_entrypoint_bundle(' in text
    assert 'execute_with_entrypoint_span(' in text
    assert 'run_default_execute_call(' in text


def test_runtime_executor_uses_entrypoint_bundle() -> None:
    text = _read('runtime/executor.py')
    assert 'build_executor_entrypoint_bundle(' in text
    assert 'entrypoint_bundle.run(executor=self, env=env)' in text
