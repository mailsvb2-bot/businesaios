from __future__ import annotations

from pathlib import Path

from lock.economic_sealed_execution_lock import (
    ALLOWED_EXECUTION_GATEWAY_IMPORTERS,
    FORBIDDEN_DIRECT_SEALED_RUNTIME_MARKERS,
    FORBIDDEN_EXECUTION_GATEWAY_IMPORTERS,
    FORBIDDEN_SECOND_BRAIN_MARKERS,
)

_GATEWAY_IMPORT_PATTERNS = (
    'from runtime.executor import build_click_provider_dispatch_execution_contract',
    'from runtime.executor import build_spend_runtime_execution_contract',
    'from runtime.executor import build_click_provider_dispatch_execution_contract, build_spend_runtime_execution_contract',
)


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_execution_gateway_helpers_are_only_imported_by_allowed_callers() -> None:
    root = _root()
    offenders: list[str] = []
    for path in root.rglob('*.py'):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding='utf-8', errors='ignore')
        if any(pattern in text for pattern in _GATEWAY_IMPORT_PATTERNS):
            if rel not in ALLOWED_EXECUTION_GATEWAY_IMPORTERS:
                offenders.append(rel)
    assert offenders == []


def test_forbidden_callers_do_not_import_execution_gateway_helpers() -> None:
    root = _root()
    for rel in FORBIDDEN_EXECUTION_GATEWAY_IMPORTERS:
        text = (root / rel).read_text(encoding='utf-8', errors='ignore')
        assert 'build_click_provider_dispatch_execution_contract' not in text
        assert 'build_spend_runtime_execution_contract' not in text


def test_second_brain_markers_do_not_escape_lock_and_tests() -> None:
    root = _root()
    offenders: list[str] = []
    allowed_prefixes = (
        'lock/economic_sealed_execution_lock.py',
        'tests/arch/test_economic_sealed_execution_owner_lock_wave239.py',
        'tests/arch/test_economic_sealed_execution_hardening_wave240.py',
        'tests/arch/test_economic_sealed_execution_repo_sweep_wave241.py',
    )
    for path in root.rglob('*.py'):
        rel = path.relative_to(root).as_posix()
        if rel in allowed_prefixes:
            continue
        text = path.read_text(encoding='utf-8', errors='ignore')
        if any(marker in text for marker in FORBIDDEN_SECOND_BRAIN_MARKERS):
            offenders.append(rel)
    assert offenders == []


def test_sealed_runtime_markers_live_only_in_runtime_internal_and_tests() -> None:
    root = _root()
    offenders: list[str] = []
    allowed_prefixes = (
        'runtime/_internal/economic_execution_contract.py',
        'lock/economic_sealed_execution_lock.py',
        'tests/unit/client_outcome/test_economic_routes.py',
        'tests/arch/test_economic_sealed_execution_repo_sweep_wave241.py',
    )
    for path in root.rglob('*.py'):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding='utf-8', errors='ignore')
        if any(marker in text for marker in FORBIDDEN_DIRECT_SEALED_RUNTIME_MARKERS):
            if rel not in allowed_prefixes:
                offenders.append(rel)
    assert offenders == []
