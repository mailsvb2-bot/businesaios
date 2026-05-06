from __future__ import annotations

from pathlib import Path

from lock.economic_sealed_execution_lock import (
    ALLOWED_RUNTIME_INTERNAL_IMPORT_OWNERS,
    FORBIDDEN_RUNTIME_INTERNAL_IMPORTERS,
    SEALED_EXECUTION_ROUTE_PATHS,
)


def test_runtime_internal_execution_contract_is_only_imported_by_allowed_owners() -> None:
    root = Path(__file__).resolve().parents[2]
    offenders: list[str] = []
    for path in root.rglob('*.py'):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding='utf-8', errors='ignore')
        if 'runtime._internal.economic_execution_contract' not in text:
            continue
        if rel not in ALLOWED_RUNTIME_INTERNAL_IMPORT_OWNERS:
            offenders.append(rel)
    assert offenders == []


def test_public_and_owner_surfaces_do_not_import_runtime_internal_directly() -> None:
    root = Path(__file__).resolve().parents[2]
    for rel in FORBIDDEN_RUNTIME_INTERNAL_IMPORTERS:
        text = (root / rel).read_text(encoding='utf-8', errors='ignore')
        assert 'runtime._internal.economic_execution_contract' not in text
        assert 'from runtime._internal' not in text


def test_sealed_execution_routes_stay_in_public_security_guard_and_fastapi_surface() -> None:
    root = Path(__file__).resolve().parents[2]
    guard = (root / 'entrypoints' / 'api' / 'public_surface_security_guard.py').read_text(encoding='utf-8', errors='ignore')
    routes = (root / 'adapters' / 'api' / 'fastapi' / 'public_routes.py').read_text(encoding='utf-8', errors='ignore')
    for route in SEALED_EXECUTION_ROUTE_PATHS:
        assert route in guard
        assert route in routes
