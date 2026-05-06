from __future__ import annotations

from pathlib import Path


def test_sealed_execution_gateway_is_only_public_bridge_to_runtime_internal() -> None:
    root = Path(__file__).resolve().parents[2]
    gateway = (root / 'runtime' / 'executor.py').read_text(encoding='utf-8', errors='ignore')
    assert 'build_click_provider_dispatch_execution_contract' in gateway
    assert 'build_spend_runtime_execution_contract' in gateway

    route_handlers = (root / 'entrypoints' / 'api' / 'economic_route_handlers.py').read_text(encoding='utf-8', errors='ignore')
    assert 'from runtime.executor import build_click_provider_dispatch_execution_contract, build_spend_runtime_execution_contract' in route_handlers
    assert 'runtime._internal.economic_execution_contract' not in route_handlers


def test_sealed_execution_routes_are_registered_in_public_security_guard() -> None:
    root = Path(__file__).resolve().parents[2]
    guard = (root / 'entrypoints' / 'api' / 'public_surface_security_guard.py').read_text(encoding='utf-8', errors='ignore')
    required = [
        '/economic/truth/click-billing-sealed-execution/{order_id}/{lead_id}',
        '/economic/export/click-billing-sealed-execution/{order_id}/{lead_id}',
        '/economic/audit/click-billing-sealed-execution/{order_id}/{lead_id}',
        '/economic/truth/spend-external-sealed-execution/client-outcome/{order_id}/{lead_id}',
        '/economic/export/spend-external-sealed-execution/client-outcome/{order_id}/{lead_id}',
        '/economic/audit/spend-external-sealed-execution/client-outcome/{order_id}/{lead_id}',
    ]
    for item in required:
        assert item in guard
