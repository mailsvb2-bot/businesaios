from __future__ import annotations

import ast
from pathlib import Path

from runtime.canonical_surface_manifest import (
    ALLOWED_NETWORK_LITERAL_SURFACES,
    ALLOWED_NETWORK_PRIMITIVE_IMPORTERS,
    ALLOWED_OPERATOR_NETWORK_PROBES,
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

NETWORK_IMPORT_ROOTS = {"requests", "httpx", "aiohttp", "urllib3", "socket"}
EXPLICIT_NETWORK_IMPORTS = {"urllib.request"}
SUBPROCESS_NETWORK_BINARIES = {"curl", "wget"}

EXTERNAL_API_LITERAL_TOKENS = (
    "api.telegram.org",
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


def _iter_python_files() -> tuple[Path, ...]:
    files: list[Path] = []
    for path in PROJECT_ROOT.rglob("*.py"):
        if path.is_file() and not _is_ignored(path):
            files.append(path)
    return tuple(files)


def _iter_literal_files() -> tuple[Path, ...]:
    suffixes = {".py", ".sh", ".env", ".example", ".yml", ".yaml", ".toml"}
    files: list[Path] = []
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file() or _is_ignored(path):
            continue
        if path.suffix.lower() in suffixes or path.name in {"Dockerfile", ".env.example"}:
            files.append(path)
    return tuple(files)


def _parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))


def _full_attr_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _full_attr_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _network_import_offenses(tree: ast.AST) -> list[str]:
    offenses: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                root = name.split(".", 1)[0]
                if root in NETWORK_IMPORT_ROOTS or name in EXPLICIT_NETWORK_IMPORTS:
                    offenses.append(f"import {name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0]
            imported_names = {alias.name for alias in node.names}
            if root in NETWORK_IMPORT_ROOTS or module in EXPLICIT_NETWORK_IMPORTS:
                offenses.append(f"from {module} import")
            if module == "urllib" and "request" in imported_names:
                offenses.append("from urllib import request")
    return offenses


def _import_aliases(tree: ast.AST) -> tuple[set[str], set[str], set[str]]:
    imported_urlopen_names: set[str] = set()
    imported_request_module_aliases: set[str] = set()
    imported_subprocess_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "urllib.request":
                    imported_request_module_aliases.add(alias.asname or "urllib.request")
                if alias.name == "subprocess":
                    imported_subprocess_aliases.add(alias.asname or "subprocess")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "urllib.request":
                for alias in node.names:
                    if alias.name == "urlopen":
                        imported_urlopen_names.add(alias.asname or alias.name)
            if module == "urllib" and any(alias.name == "request" for alias in node.names):
                imported_request_module_aliases.add("request")
            if module == "subprocess":
                for alias in node.names:
                    if alias.name in {"run", "Popen", "call", "check_call", "check_output"}:
                        imported_subprocess_aliases.add(alias.asname or alias.name)
    return imported_urlopen_names, imported_request_module_aliases, imported_subprocess_aliases


def _network_call_offenses(tree: ast.AST) -> list[str]:
    offenses: list[str] = []
    imported_urlopen_names, imported_request_module_aliases, imported_subprocess_aliases = _import_aliases(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call_name = _full_attr_name(node.func)
        if call_name in imported_urlopen_names or call_name.endswith(".urlopen"):
            offenses.append(call_name)
        if any(call_name == f"{alias}.urlopen" for alias in imported_request_module_aliases):
            offenses.append(call_name)
        if _is_subprocess_network_call(node=node, call_name=call_name, subprocess_aliases=imported_subprocess_aliases):
            offenses.append(call_name)
    return offenses


def _is_subprocess_network_call(*, node: ast.Call, call_name: str, subprocess_aliases: set[str]) -> bool:
    subprocess_call_names = {
        "subprocess.run",
        "subprocess.Popen",
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
        *subprocess_aliases,
    }
    if call_name not in subprocess_call_names:
        return False
    if not node.args:
        return False
    first = node.args[0]
    if isinstance(first, ast.List) and first.elts:
        head = first.elts[0]
        return isinstance(head, ast.Constant) and str(head.value) in SUBPROCESS_NETWORK_BINARIES
    if isinstance(first, ast.Tuple) and first.elts:
        head = first.elts[0]
        return isinstance(head, ast.Constant) and str(head.value) in SUBPROCESS_NETWORK_BINARIES
    if isinstance(first, ast.Constant):
        return str(first.value).split(maxsplit=1)[0] in SUBPROCESS_NETWORK_BINARIES
    return False


def _network_primitive_offenses(path: Path) -> list[str]:
    try:
        tree = _parse(path)
    except SyntaxError:
        return []
    return [*_network_import_offenses(tree), *_network_call_offenses(tree)]


def test_no_direct_network_primitives_outside_sealed_effects_or_provider_transport() -> None:
    offenders: list[str] = []
    allowed = set(ALLOWED_NETWORK_PRIMITIVE_IMPORTERS) | set(ALLOWED_OPERATOR_NETWORK_PROBES)
    for path in _iter_python_files():
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        if rel.startswith("tests/"):
            continue
        offenses = _network_primitive_offenses(path)
        if offenses and rel not in allowed:
            offenders.append(f"{rel}:{','.join(sorted(set(offenses)))}")
    assert offenders == []


def test_no_subprocess_curl_or_wget_outside_tests() -> None:
    offenders: list[str] = []
    allowed = set(ALLOWED_OPERATOR_NETWORK_PROBES)
    for path in _iter_python_files():
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        if rel.startswith("tests/"):
            continue
        try:
            tree = _parse(path)
        except SyntaxError:
            continue
        imported_subprocess_aliases = _import_aliases(tree)[2]
        call_offenses = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call_name = _full_attr_name(node.func)
                if _is_subprocess_network_call(node=node, call_name=call_name, subprocess_aliases=imported_subprocess_aliases):
                    call_offenses.append(call_name)
        if call_offenses and rel not in allowed:
            offenders.append(f"{rel}:{','.join(sorted(set(call_offenses)))}")
    assert offenders == []


def test_external_api_literals_are_only_in_sealed_effects_or_provider_transport() -> None:
    offenders: list[str] = []
    allowed = set(ALLOWED_NETWORK_LITERAL_SURFACES)
    for path in _iter_literal_files():
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        if rel.startswith("tests/"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        hits = [token for token in EXTERNAL_API_LITERAL_TOKENS if token in text]
        if hits and rel not in allowed:
            offenders.append(f"{rel}:{','.join(hits)}")
    assert offenders == []


def test_provider_transport_files_are_the_only_business_autonomy_network_allowed_surfaces() -> None:
    assert "runtime/business_autonomy/provider_http_live_clients.py" in ALLOWED_NETWORK_PRIMITIVE_IMPORTERS
    assert "runtime/business_autonomy/provider_vendor_transports.py" in ALLOWED_NETWORK_PRIMITIVE_IMPORTERS
    assert "runtime/business_autonomy/provider_http_live_clients.py" in ALLOWED_NETWORK_LITERAL_SURFACES
    assert "runtime/business_autonomy/provider_vendor_transports.py" in ALLOWED_NETWORK_LITERAL_SURFACES
    assert "runtime/business_autonomy/provider_transport_bindings.py" in ALLOWED_NETWORK_LITERAL_SURFACES


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
    for path in _iter_python_files():
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        if rel.startswith("tests/") or not rel.startswith(sensitive_prefixes):
            continue
        offenses = _network_primitive_offenses(path)
        if offenses:
            offenders.append(f"{rel}:{','.join(sorted(set(offenses)))}")
    assert offenders == []


def test_operator_network_probes_are_local_server_only() -> None:
    for rel in ALLOWED_OPERATOR_NETWORK_PROBES:
        path = PROJECT_ROOT / rel
        assert path.exists(), rel
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert "CANON_SERVER_HEALTH_PROBE" in text or "CANON_SERVER_SMOKE_FLOW" in text or "127.0.0.1" in text or "localhost" in text
        assert not any(token in text for token in EXTERNAL_API_LITERAL_TOKENS), rel
