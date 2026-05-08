from __future__ import annotations

from pathlib import Path

from runtime.canonical_surface_manifest import (
    ALLOWED_NETWORK_LITERAL_SURFACES,
    ALLOWED_NETWORK_PRIMITIVE_IMPORTERS,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

IGNORED_PARTS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "data",
    "runtime_state",
    "_audit",
}

NETWORK_PRIMITIVE_TOKENS = (
    "import requests",
    "from requests import",
    "import httpx",
    "from httpx import",
    "import aiohttp",
    "from aiohttp import",
    "import urllib3",
    "from urllib3 import",
    "import socket",
    "from socket import",
    "from urllib import request",
    "import urllib.request",
    "from urllib.request import",
    "urlopen(",
    "Request(",
)

SUBPROCESS_NETWORK_TOKENS = (
    "subprocess.run(['curl'",
    'subprocess.run(["curl"',
    "subprocess.Popen(['curl'",
    'subprocess.Popen(["curl"',
    "subprocess.call(['curl'",
    'subprocess.call(["curl"',
    "subprocess.run(['wget'",
    'subprocess.run(["wget"',
    "subprocess.Popen(['wget'",
    'subprocess.Popen(["wget"',
    "subprocess.call(['wget'",
    'subprocess.call(["wget"',
)

EXTERNAL_API_LITERAL_TOKENS = (
    "api.telegram.org",
    "TELEGRAM_BOT_TOKEN",
    "YOOKASSA",
    "graph.facebook.com",
    "googleapis.com",
    "googleads.googleapis.com",
    "business-api.tiktok.com",
    "api.hubapi.com",
    "myshopify.com",
    "woocommerce.com",
)


def _is_ignored(path: Path) -> bool:
    rel_parts = path.relative_to(PROJECT_ROOT).parts
    return any(part in IGNORED_PARTS for part in rel_parts)


def _iter_source_files() -> tuple[Path, ...]:
    suffixes = {".py", ".sh", ".env", ".example", ".yml", ".yaml", ".toml"}
    files: list[Path] = []
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file() or _is_ignored(path):
            continue
        if path.suffix.lower() in suffixes or path.name in {"Dockerfile", ".env.example"}:
            files.append(path)
    return tuple(files)


def test_no_direct_network_primitives_outside_sealed_effects_or_provider_transport() -> None:
    offenders: list[str] = []
    allowed = set(ALLOWED_NETWORK_PRIMITIVE_IMPORTERS)
    for path in _iter_source_files():
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        if rel.startswith("tests/"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(token in text for token in NETWORK_PRIMITIVE_TOKENS) and rel not in allowed:
            offenders.append(rel)
    assert offenders == []


def test_no_subprocess_curl_or_wget_outside_tests() -> None:
    offenders: list[str] = []
    for path in _iter_source_files():
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        if rel.startswith("tests/"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(token in text for token in SUBPROCESS_NETWORK_TOKENS):
            offenders.append(rel)
    assert offenders == []


def test_external_api_literals_are_only_in_sealed_effects_or_provider_transport() -> None:
    offenders: list[str] = []
    allowed = set(ALLOWED_NETWORK_LITERAL_SURFACES)
    for path in _iter_source_files():
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        if rel.startswith("tests/"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(token in text for token in EXTERNAL_API_LITERAL_TOKENS) and rel not in allowed:
            offenders.append(rel)
    assert offenders == []


def test_provider_transport_files_are_the_only_business_autonomy_network_allowed_surfaces() -> None:
    assert "runtime/business_autonomy/provider_http_live_clients.py" in ALLOWED_NETWORK_PRIMITIVE_IMPORTERS
    assert "runtime/business_autonomy/provider_vendor_transports.py" in ALLOWED_NETWORK_PRIMITIVE_IMPORTERS
    assert "runtime/business_autonomy/provider_http_live_clients.py" in ALLOWED_NETWORK_LITERAL_SURFACES
    assert "runtime/business_autonomy/provider_vendor_transports.py" in ALLOWED_NETWORK_LITERAL_SURFACES


def test_decision_and_admin_surfaces_do_not_import_network_primitives() -> None:
    sensitive_prefixes = (
        "core/",
        "application/",
        "app/web/",
        "adapters/api/",
        "entrypoints/api/",
        "connectors/",
        "execution/",
    )
    offenders: list[str] = []
    for path in _iter_source_files():
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        if rel.startswith("tests/") or not rel.startswith(sensitive_prefixes):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(token in text for token in NETWORK_PRIMITIVE_TOKENS + SUBPROCESS_NETWORK_TOKENS):
            offenders.append(rel)
    assert offenders == []
