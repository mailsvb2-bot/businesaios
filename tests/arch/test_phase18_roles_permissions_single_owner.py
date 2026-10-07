from __future__ import annotations

from pathlib import Path

from governance.permission_matrix import PermissionMatrix
from governance.rbac_contract import Permission, RoleId
from governance.role_catalog import RoleCatalog


ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_AUTH_ROOTS = (
    ROOT / "governance",
    ROOT / "entrypoints" / "api",
    ROOT / "execution",
    ROOT / "runtime" / "guard",
)


def test_product_ux_roles_never_enter_authorization_owners() -> None:
    needles = ("core.users.roles", "UserRoleInfo", "user:role")
    offenders: list[str] = []
    for root in FORBIDDEN_AUTH_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if any(needle in text for needle in needles):
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_governance_role_catalog_and_permission_matrix_are_the_authority() -> None:
    catalog = RoleCatalog()
    matrix = PermissionMatrix()

    assert catalog.is_known_role(RoleId.OWNER)
    assert catalog.is_known_role(RoleId.OPERATOR)
    assert matrix.permissions_for_role(RoleId.OWNER) >= {
        Permission.VIEW_AUDIT,
        Permission.EXECUTE_SAFE_READ,
        Permission.EXECUTE_OUTBOUND,
        Permission.EXECUTE_PUBLICATION,
        Permission.EXECUTE_BUDGET_CHANGE,
        Permission.APPROVE_CHANGE,
    }
    assert Permission.EXECUTE_BUDGET_CHANGE not in matrix.permissions_for_role(RoleId.OPERATOR)
