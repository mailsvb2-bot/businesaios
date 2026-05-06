from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from governance.rbac_contract import RoleCatalogContract, RoleId


CANON_GOVERNANCE_ROLE_CATALOG = True


@dataclass(frozen=True)
class RoleDefinition:
    role_id: RoleId
    title: str
    description: str
    service_role: bool = False
    human_approver_role: bool = True


_ROLE_DEFINITIONS: dict[RoleId, RoleDefinition] = {
    RoleId.SYSTEM: RoleDefinition(
        role_id=RoleId.SYSTEM,
        title="System",
        description="Trusted internal service role. Never valid as a human approval authority.",
        service_role=True,
        human_approver_role=False,
    ),
    RoleId.OWNER: RoleDefinition(
        role_id=RoleId.OWNER,
        title="Owner",
        description="Tenant owner with final business authority.",
    ),
    RoleId.OPERATOR: RoleDefinition(
        role_id=RoleId.OPERATOR,
        title="Operator",
        description="Bounded operational executor.",
    ),
    RoleId.ANALYST: RoleDefinition(
        role_id=RoleId.ANALYST,
        title="Analyst",
        description="Read-heavy and advisory role.",
    ),
    RoleId.FINANCE: RoleDefinition(
        role_id=RoleId.FINANCE,
        title="Finance",
        description="Finance authority for spend and cost-sensitive controls.",
    ),
    RoleId.AUDITOR: RoleDefinition(
        role_id=RoleId.AUDITOR,
        title="Auditor",
        description="Audit visibility role.",
    ),
    RoleId.SECURITY: RoleDefinition(
        role_id=RoleId.SECURITY,
        title="Security",
        description="Security and production-risk authority.",
    ),
    RoleId.SUPPORT: RoleDefinition(
        role_id=RoleId.SUPPORT,
        title="Support",
        description="Narrow customer-facing support operations.",
    ),
    RoleId.VIEWER: RoleDefinition(
        role_id=RoleId.VIEWER,
        title="Viewer",
        description="Read-only role.",
    ),
}


class RoleCatalog(RoleCatalogContract):
    def is_known_role(self, role_id: RoleId) -> bool:
        return role_id in _ROLE_DEFINITIONS

    def normalize_roles(self, role_ids: frozenset[RoleId]) -> frozenset[RoleId]:
        return frozenset(role for role in role_ids if role in _ROLE_DEFINITIONS)

    def definitions(self) -> tuple[RoleDefinition, ...]:
        return tuple(_ROLE_DEFINITIONS.values())

    def is_human_approver_role(self, role_id: RoleId) -> bool:
        definition = _ROLE_DEFINITIONS.get(role_id)
        return bool(definition is not None and definition.human_approver_role)


def known_roles() -> tuple[RoleId, ...]:
    return tuple(_ROLE_DEFINITIONS.keys())


def ensure_known_roles(role_ids: Iterable[RoleId]) -> frozenset[RoleId]:
    result = frozenset(role_ids)
    unknown = [role for role in result if role not in _ROLE_DEFINITIONS]
    if unknown:
        raise ValueError(f"unknown roles: {', '.join(sorted(str(x.value) for x in unknown))}")
    return result


__all__ = [
    "CANON_GOVERNANCE_ROLE_CATALOG",
    "RoleCatalog",
    "RoleDefinition",
    "ensure_known_roles",
    "known_roles",
]
