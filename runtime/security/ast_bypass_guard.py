"""Static bypass detector (AST).

CI-level architectural stop.

Goal:
  Prevent any code in the repository from importing / calling side-effect
  entrypoints outside RuntimeExecutor.

Notes:
  - Conservative by design.
  - Complements (does not replace) runtime firewalls.
"""

from __future__ import annotations

import ast
from pathlib import Path

from canon.repository_sources import (
    RepositorySourceError,
    iter_repository_python_files,
    read_utf8_source,
    validate_repository_root,
)

# Private effects implementation must never be imported outside runtime/executor.py
FORBIDDEN_MODULE_PREFIXES = ("runtime._internal",)

# External side-effect domains that must never be imported directly.
# NOTE: Network libraries are also forbidden everywhere except the sealed effects impl.
FORBIDDEN_MODULES = {
    "payments",
    "messaging",
    "external_api",
    "requests",
    "httpx",
    "urllib3",
    "socket",
    "aiohttp",
    "subprocess",
}
FORBIDDEN_MODULE_PATHS = {"urllib.request"}
NETWORK_MODULES = {"requests", "httpx", "urllib3", "socket", "aiohttp"}
NETWORK_MODULE_PATHS = {"urllib.request"}

# Direct calls that must not exist as free functions in domain code.
FORBIDDEN_CALL_NAMES = {
    "send_message",
    "create_payment",
    "capture_payment",
    "deploy_policy",
    "rollback_policy",
}
FORBIDDEN_CALL_PATHS = {
    "subprocess.Popen",
    "subprocess.run",
    "subprocess.check_call",
    "subprocess.check_output",
    "os.system",
    "urllib.request.urlopen",
    "urllib.request.urlretrieve",
    "socket.connect",
    "socket.create_connection",
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
    return rel in {
        "runtime/executor.py",
        "runtime/admin_state_support.py",
        "runtime/execution/provider_outbound_sender.py",
    }


class _Visitor(ast.NodeVisitor):
    def __init__(self, rel: str):
        self.rel = rel
        self.violations: list[str] = []
        self._module_aliases: dict[str, str] = {}
        self._forbidden_call_aliases: set[str] = set()

    @staticmethod
    def _is_forbidden_module(module: str) -> bool:
        if module in FORBIDDEN_MODULE_PATHS or any(module.startswith(path + ".") for path in FORBIDDEN_MODULE_PATHS):
            return True
        head = module.split(".", 1)[0]
        return head in FORBIDDEN_MODULES

    def _network_import_allowed(self, module: str) -> bool:
        network_module = (
            module in NETWORK_MODULE_PATHS
            or any(module.startswith(path + ".") for path in NETWORK_MODULE_PATHS)
            or module.split(".", 1)[0] in NETWORK_MODULES
        )
        return self.rel == ALLOWED_NETWORK_FILE and network_module

    def _record_forbidden_import(
        self,
        *,
        module: str,
        line: int,
        from_import: bool,
    ) -> None:
        if self._network_import_allowed(module):
            return
        prefix = "from" if from_import else "import"
        suffix = " import …" if from_import else ""
        self.violations.append(f"{self.rel}:{line} -> {prefix} {module}{suffix}")

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for imported in node.names:
            module = imported.name
            local_name = imported.asname or module.split(".", 1)[0]
            self._module_aliases[local_name] = module
            if any(module.startswith(prefix) for prefix in FORBIDDEN_MODULE_PREFIXES):
                if not _is_allowed_file(self.rel):
                    self._record_forbidden_import(
                        module=module,
                        line=node.lineno,
                        from_import=False,
                    )
            elif self._is_forbidden_module(module):
                self._record_forbidden_import(
                    module=module,
                    line=node.lineno,
                    from_import=False,
                )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if int(getattr(node, "level", 0) or 0) > 0:
            return
        module = node.module or ""
        for imported in node.names:
            if imported.name == "*":
                continue
            path = f"{module}.{imported.name}" if module else imported.name
            local_name = imported.asname or imported.name
            if path in FORBIDDEN_CALL_PATHS:
                self._forbidden_call_aliases.add(local_name)
        if any(module.startswith(prefix) for prefix in FORBIDDEN_MODULE_PREFIXES):
            if not _is_allowed_file(self.rel):
                self._record_forbidden_import(
                    module=module,
                    line=node.lineno,
                    from_import=True,
                )
            return
        forbidden = self._is_forbidden_module(module)
        if module == "urllib":
            forbidden = any(imported.name == "request" for imported in node.names)
        if forbidden:
            self._record_forbidden_import(
                module=module,
                line=node.lineno,
                from_import=True,
            )

    def _call_path(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return self._module_aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            base = self._call_path(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        return ""

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        call_path = self._call_path(node.func)
        if isinstance(node.func, ast.Name) and (
            node.func.id in FORBIDDEN_CALL_NAMES or node.func.id in self._forbidden_call_aliases
        ):
            self.violations.append(f"{self.rel}:{node.lineno} -> call {node.func.id}(…)")
        elif call_path in FORBIDDEN_CALL_PATHS:
            self.violations.append(f"{self.rel}:{node.lineno} -> call {call_path}(…)")

        dynamic_module: str | None = None
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "importlib"
            and node.func.attr == "import_module"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ) or (
            isinstance(node.func, ast.Name)
            and node.func.id == "__import__"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            dynamic_module = node.args[0].value

        if dynamic_module is not None:
            private = any(dynamic_module.startswith(prefix) for prefix in FORBIDDEN_MODULE_PREFIXES)
            external = self._is_forbidden_module(dynamic_module)
            if (private and not _is_allowed_file(self.rel)) or (
                external and not self._network_import_allowed(dynamic_module)
            ):
                self.violations.append(f"{self.rel}:{node.lineno} -> dynamic import {dynamic_module!r}")

        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == "_internal"
            and not _is_allowed_file(self.rel)
        ):
            self.violations.append(f"{self.rel}:{node.lineno} -> getattr(…, '_internal')")

        self.generic_visit(node)


def scan_repo(root: Path) -> None:
    try:
        repo = validate_repository_root(root)
    except ValueError as exc:
        raise RuntimeError("DECISION_BYPASS_DETECTED\n.:0 -> SCAN_ROOT_ERROR: " + str(exc)) from exc

    violations: list[str] = []
    try:
        paths = iter_repository_python_files(
            repo,
            excluded_prefixes=EXCLUDED_PREFIXES + ("runtime/_internal/",),
        )
        for py in paths:
            rel = py.relative_to(repo).as_posix()
            try:
                src = read_utf8_source(py)
            except RepositorySourceError as exc:
                violations.append(f"{rel}:0 -> SOURCE_READ_ERROR: {type(exc.__cause__).__name__}")
                continue

            try:
                tree = ast.parse(src, filename=str(py))
            except (SyntaxError, ValueError) as exc:
                violations.append(f"{rel}:{getattr(exc, 'lineno', 0) or 0} -> SYNTAX_ERROR")
                continue

            visitor = _Visitor(rel)
            visitor.visit(tree)
            violations.extend(visitor.violations)
    except RepositorySourceError as exc:
        violations.append(f".:0 -> SOURCE_SCAN_ERROR: {exc}")

    if violations:
        raise RuntimeError("DECISION_BYPASS_DETECTED\n" + "\n".join(sorted(set(violations))))
