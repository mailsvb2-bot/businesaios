from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOTS = (
    "application",
    "billing",
    "core",
    "crm",
    "execution",
    "governance",
    "interfaces",
    "runtime",
)


def test_businessaios_runtime_has_no_clientplatform_import_dependency() -> None:
    violations: list[str] = []
    for root_name in RUNTIME_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("clientplatform"):
                    violations.append(f"{path.relative_to(ROOT)} imports {node.module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("clientplatform"):
                            violations.append(f"{path.relative_to(ROOT)} imports {alias.name}")
    assert not violations, "\n".join(violations)
