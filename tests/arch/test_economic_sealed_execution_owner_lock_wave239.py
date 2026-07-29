from __future__ import annotations

from pathlib import Path

from lock.economic_sealed_execution_lock import SEALED_EXECUTION_ROUTE_PATHS


def test_sealed_execution_gateway_is_only_public_bridge_to_runtime_internal() -> None:
    root = Path(__file__).resolve().parents[2]
    gateway = (root / 'runtime' / 'executor.py').read_text(encoding='utf-8', errors='ignore')
    assert 'build_click_provider_dispatch_execution_contract' in gateway
    assert 'build_spend_runtime_execution_contract' in gateway

    route_handlers = (root / 'entrypoints' / 'api' / 'economic_route_handlers.py').read_text(encoding='utf-8', errors='ignore')
    assert 'from runtime.economic_execution import (' in route_handlers
    assert 'runtime._internal.economic_execution_contract' not in route_handlers


def test_sealed_execution_routes_are_registered_in_public_security_specs() -> None:
    root = Path(__file__).resolve().parents[2]
    route_specs = (root / 'entrypoints' / 'api' / 'public_surface_route_specs.py').read_text(encoding='utf-8', errors='ignore')
    guard = (root / 'entrypoints' / 'api' / 'public_surface_security_guard.py').read_text(encoding='utf-8', errors='ignore')
    for item in SEALED_EXECUTION_ROUTE_PATHS:
        assert item in route_specs
    assert '_ROUTE_SPECS.get(str(route_path).strip())' in guard
