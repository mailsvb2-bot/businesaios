from __future__ import annotations

import ast
from pathlib import Path

from application.business_autonomy.contracts import (
    AGENT_IDENTITY_SCHEMA_VERSION,
    CANON_AGENT_IDENTITY_CONTRACT,
    AgentIdentity,
)
from application.business_autonomy.registry import (
    AGENT_FACT_TYPES,
    CANON_AGENT_DELEGATION_GRAPH,
    CANON_AGENT_IDENTITY_LIFECYCLE_OWNER,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_OWNER = Path("application/business_autonomy/contracts.py")
LIFECYCLE_OWNER = Path("application/business_autonomy/registry.py")
AGENT_FACTS = {"agent.registered", "agent.revoked"}


def _production_python_files():
    for root_name in (
        "application",
        "runtime",
        "storage",
        "core",
        "adapters",
        "billing",
        "crm",
        "products",
        "contracts",
    ):
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_agent_identity_contract_and_lifecycle_markers_are_single_owner() -> None:
    contract_owners: list[Path] = []
    lifecycle_owners: list[Path] = []
    delegation_owners: list[Path] = []
    fact_owners: set[Path] = set()

    for path in _production_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(ROOT)
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                names = {target.id for target in node.targets if isinstance(target, ast.Name)}
                if node.value.value is True:
                    if "CANON_AGENT_IDENTITY_CONTRACT" in names:
                        contract_owners.append(relative)
                    if "CANON_AGENT_IDENTITY_LIFECYCLE_OWNER" in names:
                        lifecycle_owners.append(relative)
                    if "CANON_AGENT_DELEGATION_GRAPH" in names:
                        delegation_owners.append(relative)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in AGENT_FACTS:
                    fact_owners.add(relative)

    assert contract_owners == [CONTRACT_OWNER]
    assert lifecycle_owners == [LIFECYCLE_OWNER]
    assert delegation_owners == [LIFECYCLE_OWNER]
    assert fact_owners == {LIFECYCLE_OWNER}


def test_agent_identity_contract_is_versioned_and_business_scoped() -> None:
    assert CANON_AGENT_IDENTITY_CONTRACT is True
    assert CANON_AGENT_IDENTITY_LIFECYCLE_OWNER is True
    assert CANON_AGENT_DELEGATION_GRAPH is True
    assert AGENT_IDENTITY_SCHEMA_VERSION == 1
    assert AGENT_FACT_TYPES == frozenset(AGENT_FACTS)

    fields = set(AgentIdentity.__dataclass_fields__)
    assert {
        "agent_id",
        "agent_type",
        "agent_version",
        "tenant_id",
        "business_id",
        "delegated_by",
        "policy_profile",
        "capability_scope",
        "budget_scope",
        "risk_scope",
        "data_scope",
    }.issubset(fields)


def test_agent_identity_has_no_parallel_production_module() -> None:
    forbidden = (
        ROOT / "application/agent_identity.py",
        ROOT / "contracts/agent_identity.py",
    )
    assert all(not path.exists() for path in forbidden)
