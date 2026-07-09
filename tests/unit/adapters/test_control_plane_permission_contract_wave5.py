from __future__ import annotations

import ast
from pathlib import Path

from governance.rbac_contract import Permission


def test_control_plane_routes_reference_existing_permission_members() -> None:
    path = Path("adapters/api/fastapi/control_plane_routes.py")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    allowed = set(Permission.__members__)

    used: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        if not isinstance(node.value, ast.Name):
            continue
        if node.value.id != "Permission":
            continue
        used.add(node.attr)

    assert used
    assert used <= allowed
    assert "MANAGE_CONNECTORS" not in used
