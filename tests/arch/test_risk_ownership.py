from __future__ import annotations

import ast
from pathlib import Path

import pytest

from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity
from contracts.risk import CANON_RISK_ENTITY_CONTRACT, CANON_RISK_SEVERITY_CONTRACT, Risk, RiskLevel
from core.experiments.enums import RiskLevel as ExperimentRiskLevel
from core.experiments.enums import RolloutDecision
from core.experiments.errors import UnsafeRolloutViolation
from core.experiments.guards.unsafe_rollout_guard import UnsafeRolloutGuard
from core.experiments.policies.rollout_policy import ConservativeRolloutPolicy
from core.human_governance.enums import RiskLevel as GovernanceRiskLevel
from runtime.platform.support.safety import RiskLevel as RuntimeRiskLevel

ROOT = Path(__file__).resolve().parents[2]
OWNER = Path("contracts/risk.py")


def _production_python_files():
    for root_name in ("contracts", "application", "runtime", "storage", "core", "adapters", "billing", "crm", "products"):
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_risk_inventory_names_canonical_entity_and_severity_owner() -> None:
    row = ontology_ownership_by_entity()["Risk"]
    assert row.status is OwnershipAuditStatus.DONE
    assert row.authoritative_module == "contracts.risk"
    assert row.storage_owner == "runtime.platform.event_store"
    assert row.allowed_writers == ("application.risk",)
    assert row.allowed_readers == (
        "application.risk",
        "core.experiments.enums",
        "core.human_governance.enums",
        "runtime.platform.support.safety",
    )


def test_generic_risk_level_definition_is_unique() -> None:
    owners: list[Path] = []
    for path in _production_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(isinstance(node, ast.ClassDef) and node.name == "RiskLevel" for node in tree.body):
            owners.append(path.relative_to(ROOT))
    assert CANON_RISK_SEVERITY_CONTRACT is True
    assert owners == [OWNER]



def test_generic_risk_entity_definition_is_unique() -> None:
    owners: list[Path] = []
    for path in _production_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(isinstance(node, ast.ClassDef) and node.name == "Risk" for node in tree.body):
            owners.append(path.relative_to(ROOT))
    assert CANON_RISK_ENTITY_CONTRACT is True
    assert owners == [OWNER]
    assert Risk.__module__ == "contracts.risk"


def test_risk_registry_is_single_lifecycle_writer_and_is_runtime_wired() -> None:
    owners: list[Path] = []
    for path in _production_python_files():
        text = path.read_text(encoding="utf-8")
        if "CANON_RISK_LIFECYCLE_OWNER = True" in text:
            owners.append(path.relative_to(ROOT))
    assert owners == [Path("application/risk.py")]
    source = (ROOT / "application/risk.py").read_text(encoding="utf-8")
    assert "EventFactLifecycleWriter" in source
    wiring = (ROOT / "runtime/business_autonomy/ontology_runtime.py").read_text(encoding="utf-8")
    assert '"_risk_registry"' in wiring
    assert "RiskRegistry(event_store=event_store, idempotency_store=idempotency_store)" in wiring

def test_existing_risk_surfaces_reexport_canonical_severity() -> None:
    assert ExperimentRiskLevel is RiskLevel
    assert GovernanceRiskLevel is RiskLevel
    assert RuntimeRiskLevel is RiskLevel


def test_critical_experiment_risk_fails_closed() -> None:
    policy = ConservativeRolloutPolicy()
    assert policy.evaluate(significant=True, uplift=1.0, risk_level=RiskLevel.CRITICAL) is RolloutDecision.BLOCK

    guard = UnsafeRolloutGuard()
    with pytest.raises(UnsafeRolloutViolation, match="full rollout forbidden"):
        guard.ensure_safe(decision=RolloutDecision.FULL, risk_level=RiskLevel.CRITICAL, significant=True)
    with pytest.raises(UnsafeRolloutViolation, match="partial rollout forbidden"):
        guard.ensure_safe(decision=RolloutDecision.PARTIAL, risk_level=RiskLevel.CRITICAL, significant=True)
