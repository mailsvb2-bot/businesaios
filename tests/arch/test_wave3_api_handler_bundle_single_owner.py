from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_api_handler_bundle_is_single_owner_surface() -> None:
    text = _text('interfaces/api/api_handler_bundle.py')
    assert 'CANON_API_HANDLER_BUNDLE_SINGLE_OWNER = True' in text
    assert 'CANON_API_HANDLER_BUNDLE_NO_DECISION_LOGIC = True' in text
    assert 'def build_api_handler_bundle(' in text


def test_api_handler_bundle_reuses_one_headless_runtime_provider_and_execute_action_port_provider() -> None:
    text = _text('interfaces/api/api_handler_bundle.py')
    assert 'runtime_provider = headless_runtime_provider or build_default_headless_runtime_provider()' in text
    assert 'execute_action_port_provider = build_execute_action_port_provider(' in text
    assert 'build_headless_route_handlers(runtime_provider=runtime_provider)' in text
    assert 'build_business_memory_route_handlers(runtime_provider=runtime_provider)' in text
