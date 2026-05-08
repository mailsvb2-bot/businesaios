from __future__ import annotations
from pathlib import Path
from runtime.canonical_surface_manifest import (
    ALLOWED_BOOTSTRAP_COMPAT_IMPORTERS,
    ALLOWED_EFFECT_DOMAIN_ENTRYPOINTS,
    ALLOWED_EFFECT_ROUTER_IMPORTERS,
    ALLOWED_NETWORK_LITERAL_SURFACES,
    ALLOWED_NETWORK_PRIMITIVE_IMPORTERS,
    CANONICAL_BOOTSTRAP_OWNER_MODULES,
    CANONICAL_OWNER_PUBLIC_APIS,
    CANONICAL_ROUTE_OWNER_MODULES,
    COMPATIBILITY_PUBLIC_APIS,
    EVIDENCE_ONLY_ROUTE_HELPERS,
    LEGACY_BOOTSTRAP_COMPAT_MODULES,
)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
def _iter_py_files() -> list[Path]:
    excluded_parts = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "build",
        "dist",
        "htmlcov",
        "_audit",
    }
    return [
        p
        for p in PROJECT_ROOT.rglob("*.py")
        if not any(part in excluded_parts for part in p.relative_to(PROJECT_ROOT).parts)
    ]
def test_bootstrap_surfaces_are_marked_as_compat_and_point_to_one_owner() -> None:
    assert 'runtime.bootstrap' in CANONICAL_BOOTSTRAP_OWNER_MODULES
    expected_markers = {
        'boot/__init__.py': 'CANON_LEGACY_BOOTSTRAP_PACKAGE_SHIM = True',
        'boot/facade.py': 'CANON_LEGACY_BOOTSTRAP_SHIM = True',
        'boot/app_boot.py': 'CANON_LEGACY_BOOTSTRAP_SHIM = True',
        'boot/app_boot_surface.py': 'CANON_LEGACY_BOOTSTRAP_SHIM = True',
        'boot/http_boot.py': 'CANON_LEGACY_BOOTSTRAP_SHIM = True',
        'boot/telegram_boot.py': 'CANON_LEGACY_BOOTSTRAP_SHIM = True',
        'boot/feedback_boot.py': 'CANON_BOOT_HELPER_SURFACE = True',
        'boot/observability_boot.py': 'CANON_BOOT_HELPER_SURFACE = True',
    }
    for rel, marker in expected_markers.items():
        text = (PROJECT_ROOT / rel).read_text(encoding='utf-8')
        assert marker in text, rel
        if rel == 'boot/__init__.py':
            assert 'install_public_api_alias(__name__)' in text, rel
            assert 'CANON_BOOT_PUBLIC_API_COMPAT_SHELL = True' in text, rel
        elif rel == 'boot/app_boot.py':
            assert 'CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "bootstrap.app_boot_surface"' in text, rel
        elif rel == 'boot/app_boot_surface.py':
            assert 'CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "bootstrap.app_boot_surface"' in text, rel
        else:
            if rel in {'boot/http_boot.py', 'boot/http_boot_surface.py'}:
                assert 'CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "bootstrap.http_boot_surface"' in text, rel
            elif rel == 'boot/facade.py':
                assert 'CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "bootstrap.compose"' in text, rel
            else:
                assert 'CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "runtime.bootstrap"' in text or 'CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "bootstrap.app_boot_surface"' in text or 'CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "bootstrap.http_boot_surface"' in text or rel == 'boot/__init__.py', rel
def test_non_test_code_does_not_import_bootstrap_compat_surfaces_directly() -> None:
    offenders: list[str] = []
    compat_imports = tuple(mod for mod in LEGACY_BOOTSTRAP_COMPAT_MODULES if mod != 'boot')
    for path in _iter_py_files():
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        if rel.startswith('tests/') or rel.startswith('boot/'):
            continue
        source = path.read_text(encoding='utf-8')
        if any(f'from {mod} import' in source or f'import {mod}' in source for mod in compat_imports):
            if rel not in ALLOWED_BOOTSTRAP_COMPAT_IMPORTERS:
                offenders.append(rel)
    assert offenders == []
def test_public_api_and_routing_perimeters_stay_canonical() -> None:
    assert 'runtime.application' in CANONICAL_OWNER_PUBLIC_APIS
    assert 'runtime.application.public_api' in COMPATIBILITY_PUBLIC_APIS
    assert 'core.decision.public_api' in COMPATIBILITY_PUBLIC_APIS
    assert 'execution.routing.capability_router' in CANONICAL_ROUTE_OWNER_MODULES
    assert 'execution.routing.route_continuity_memory' in EVIDENCE_ONLY_ROUTE_HELPERS
def test_effect_and_network_perimeters_remain_sealed() -> None:
    assert 'runtime/_internal/effect_router.py' in ALLOWED_EFFECT_DOMAIN_ENTRYPOINTS
    assert 'runtime/_internal/router_support.py' in ALLOWED_EFFECT_ROUTER_IMPORTERS
    network_tokens = ('import requests', 'import httpx', 'import aiohttp', 'import urllib3', 'import socket')
    literal_tokens = ('api.telegram.org', 'TELEGRAM_BOT_TOKEN', 'YOOKASSA')
    offenders: list[str] = []
    for path in _iter_py_files():
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        if rel.startswith('tests/'):
            continue
        source = path.read_text(encoding='utf-8')
        if any(tok in source for tok in network_tokens) and rel not in ALLOWED_NETWORK_PRIMITIVE_IMPORTERS:
            offenders.append(rel)
            continue
        if any(tok in source for tok in literal_tokens) and rel not in ALLOWED_NETWORK_LITERAL_SURFACES:
            offenders.append(rel)
    assert offenders == []


def test_boot_package_root_exposes_bootstrap_alias_modules() -> None:
    text = (PROJECT_ROOT / "boot/__init__.py").read_text(encoding="utf-8")
    for alias_name, owner in {
        "runtime_boot": "bootstrap.runtime_boot",
        "system_registry_boot": "bootstrap.system_registry_boot",
    }.items():
        assert f'"{alias_name}": "{owner}"' in text
    assert "CANON_BOOT_PACKAGE_ALIAS_OWNER = True" in text
