from __future__ import annotations

from pathlib import Path

from lock.economic_sealed_execution_lock import (
    ALLOWED_SEALED_EXECUTION_HELPER_OWNERS,
    ALLOWED_SEALED_ROUTE_MARKER_OWNERS,
    FORBIDDEN_GATEWAY_IMPORT_PREFIXES,
    SEALED_EXECUTION_ROUTE_PATHS,
)

_HELPER_MARKERS = (
    'build_click_provider_dispatch_execution_contract',
    'build_spend_runtime_execution_contract',
)


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_sealed_execution_helpers_are_only_referenced_by_allowed_owners() -> None:
    root = _root()
    offenders: list[str] = []
    for path in root.rglob('*.py'):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding='utf-8', errors='ignore')
        if any(marker in text for marker in _HELPER_MARKERS):
            if rel not in ALLOWED_SEALED_EXECUTION_HELPER_OWNERS:
                offenders.append(rel)
    assert offenders == []


def test_forbidden_repo_prefixes_do_not_reference_gateway_helpers() -> None:
    root = _root()
    offenders: list[str] = []
    for path in root.rglob('*.py'):
        rel = path.relative_to(root).as_posix()
        if not rel.startswith(FORBIDDEN_GATEWAY_IMPORT_PREFIXES):
            continue
        text = path.read_text(encoding='utf-8', errors='ignore')
        if any(marker in text for marker in _HELPER_MARKERS):
            offenders.append(rel)
    assert offenders == []


def test_sealed_execution_route_markers_live_only_in_allowed_surfaces() -> None:
    root = _root()
    offenders: list[str] = []
    for path in root.rglob('*.py'):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding='utf-8', errors='ignore')
        if any(route in text for route in SEALED_EXECUTION_ROUTE_PATHS):
            if rel not in ALLOWED_SEALED_ROUTE_MARKER_OWNERS:
                offenders.append(rel)
    assert offenders == []
