from __future__ import annotations

from pathlib import Path

import contracts
import interfaces
import schemas

ROOT = Path(__file__).resolve().parents[2]

def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def test_contract_schema_interface_roles_and_boundaries_stay_distinct() -> None:
    contracts_init = _read("contracts/__init__.py")
    assert "CANON_CONTRACT_NAMESPACE = True" in contracts_init
    assert "interfaces" not in contracts_init
    assert "connector" not in contracts_init

    schemas_init = _read("schemas/__init__.py")
    assert "CANON_SCHEMA_NAMESPACE = True" in schemas_init
    assert "interfaces" not in schemas_init
    assert "connector" not in schemas_init

    interfaces_init = _read("interfaces/__init__.py")
    assert "CANON_INTERFACE_NAMESPACE = True" in interfaces_init
    assert "Canonical boundary adapter and connector surface." in interfaces_init
    assert "domain contract truth" not in interfaces_init

    contracts_role = _read("contracts/CANON_NAMESPACE_ROLE.md")
    assert "canonical domain contract surface" in contracts_role
    assert "second runtime adapter surface" in contracts_role

    schemas_role = _read("schemas/CANON_NAMESPACE_ROLE.md")
    assert "validation and serialization schema surface" in schemas_role
    assert "second domain contract truth" in schemas_role

    interfaces_role = _read("interfaces/CANON_NAMESPACE_ROLE.md")
    assert "boundary adapter and connector surface" in interfaces_role
    assert "second domain contract truth" in interfaces_role

    assert contracts.CANON_CONTRACT_NAMESPACE is True
    assert schemas.CANON_SCHEMA_NAMESPACE is True
    assert interfaces.CANON_INTERFACE_NAMESPACE is True
