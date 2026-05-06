from __future__ import annotations

"""Static bypass detector (AST).

CI-level architectural stop.

Goal:
  Prevent any code in the repository from importing / calling side-effect
  entrypoints outside RuntimeExecutor.

Notes:
  - Conservative by design.
  - Complements (does not replace) runtime firewalls.
"""

import ast
from pathlib import Path

# Private effects implementation must never be imported outside runtime/executor.py
FORBIDDEN_MODULE_PREFIXES = (
    "runtime._internal",
)

# External side-effect domains that must never be imported directly.
# NOTE: Network libraries are also forbidden everywhere except the sealed effects impl.
FORBIDDEN_MODULES = {
    "payments",
    "messaging",
    "external_api",
    "requests",
    "httpx",
    "urllib",
    "urllib3",
    "socket",
    "aiohttp",
    "subprocess",
}

# Direct calls that must not exist as free functions in domain code.
FORBIDDEN_CALL_NAMES = {
    "send_message",
    "create_payment",
    "capture_payment",
    "deploy_policy",
    "rollback_policy",
    # Process primitives
    "Popen",
    "run",
    "check_call",
    "check_output",
    "system",
    # Network primitives
    "urlopen",
    "request",
    "connect",
}


# The ONLY place real integrations are allowed.
ALLOWED_NETWORK_FILE = "runtime/_internal/_effects_impl.py"

# Directories that are not part of production runtime and are excluded from bypass scan.
EXCLUDED_PREFIXES = (
    "tests/",
    "scripts/",
    "docs/",
    "ci/",
    ".github/",
    "infrastructure/",
    "runtime/sandbox/",
    "formal/",
)


def _is_allowed_file(rel: str) -> bool:
    # Sealed runtime implementation may import runtime._internal.
    if rel.startswith("runtime/_internal/"):
        return True
    # Only the canonical facades may import runtime._internal.
    return rel in {"runtime/executor.py", "runtime/effects.py"}


class _Visitor(ast.NodeVisitor):
    def __init__(self, rel: str):
        self.rel = rel
        self.violations: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for n in node.names:
            mod = n.name
            if any(mod.startswith(p) for p in FORBIDDEN_MODULE_PREFIXES):
                if not _is_allowed_file(self.rel):
                    self.violations.append(f"{self.rel}:{node.lineno} -> import {mod}")
            head = mod.split(".")[0]
            if head in FORBIDDEN_MODULES:
                if head in {"requests", "httpx", "urllib", "urllib3", "socket", "aiohttp"} and self.rel == ALLOWED_NETWORK_FILE:
                    continue
                self.violations.append(f"{self.rel}:{node.lineno} -> import {mod}")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if int(getattr(node, "level", 0) or 0) > 0:
            return
        mod = node.module or ""
        if any(mod.startswith(p) for p in FORBIDDEN_MODULE_PREFIXES):
            if not _is_allowed_file(self.rel):
                self.violations.append(f"{self.rel}:{node.lineno} -> from {mod} import …")
        head = mod.split(".")[0]
        if head in FORBIDDEN_MODULES:
            if head in {"requests", "httpx", "urllib", "urllib3", "socket", "aiohttp"} and self.rel == ALLOWED_NETWORK_FILE:
                return
            self.violations.append(f"{self.rel}:{node.lineno} -> from {mod} import …")

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        # Direct forbidden call names
        if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALL_NAMES:
            self.violations.append(f"{self.rel}:{node.lineno} -> call {node.func.id}(…)")

        # Dynamic import bypass: importlib.import_module("runtime._internal...")
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            if node.func.value.id == "importlib" and node.func.attr == "import_module":
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    mod = node.args[0].value
                    if any(mod.startswith(p) for p in FORBIDDEN_MODULE_PREFIXES):
                        if not _is_allowed_file(self.rel):
                            self.violations.append(f"{self.rel}:{node.lineno} -> importlib.import_module({mod!r})")

        # Dynamic import bypass: __import__("runtime._internal...")
        if isinstance(node.func, ast.Name) and node.func.id == "__import__":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                mod = node.args[0].value
                if any(mod.startswith(p) for p in FORBIDDEN_MODULE_PREFIXES):
                    if not _is_allowed_file(self.rel):
                        self.violations.append(f"{self.rel}:{node.lineno} -> __import__({mod!r})")

        # getattr(runtime, "_internal") bypass
        if isinstance(node.func, ast.Name) and node.func.id == "getattr":
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and node.args[1].value == "_internal":
                if not _is_allowed_file(self.rel):
                    self.violations.append(f"{self.rel}:{node.lineno} -> getattr(…, '_internal')")

        self.generic_visit(node)


def scan_repo(root: Path) -> None:
    root = root.resolve()
    violations: list[str] = []

    for py in root.rglob("*.py"):
        rel = py.relative_to(root).as_posix()
        if rel.startswith((".venv/", "__pycache__/") + EXCLUDED_PREFIXES):
            continue

        # runtime/_internal is the sealed effects implementation zone.
        # It is allowed to import transport helpers and to use url builders.
        if rel.startswith("runtime/_internal/"):
            continue
        try:
            src = py.read_text(encoding="utf-8")
        except Exception:
            continue

        try:
            tree = ast.parse(src, filename=str(py))
        except SyntaxError as e:
            violations.append(f"{rel}:{getattr(e, 'lineno', '?')} -> SYNTAX_ERROR")
            continue

        v = _Visitor(rel)
        v.visit(tree)
        violations.extend(v.violations)

    if violations:
        raise RuntimeError("DECISION_BYPASS_DETECTED\n" + "\n".join(violations))
