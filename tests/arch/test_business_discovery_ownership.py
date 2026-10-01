from __future__ import annotations

import ast
from pathlib import Path

from canon.business_ontology_inventory import (
    OwnershipAuditStatus,
    ontology_ownership_by_entity,
)

ROOT = Path(__file__).resolve().parents[2]
DISCOVERY_ROOT = ROOT / "application" / "business_discovery"


def _discovery_python_files() -> tuple[Path, ...]:
    return tuple(sorted(DISCOVERY_ROOT.rglob("*.py")))


def test_business_discovery_reuses_canonical_business_goal_constraint_and_evidence_owners() -> None:
    owners = ontology_ownership_by_entity()

    business = owners["Business"]
    assert business.status is OwnershipAuditStatus.DONE
    assert business.authoritative_module == "contracts.business_profile"

    goal = owners["Goal"]
    assert goal.status is OwnershipAuditStatus.DONE
    assert goal.authoritative_module == "contracts.business_goal"
    assert goal.allowed_writers == ("application.business_goal",)

    constraint = owners["Constraint"]
    assert constraint.status is OwnershipAuditStatus.DONE
    assert constraint.authoritative_module == "contracts.business_constraints"
    assert constraint.allowed_writers == ("application.business_constraint",)

    evidence = owners["Evidence"]
    assert evidence.status is OwnershipAuditStatus.DONE
    assert evidence.authoritative_module == "storage.evidence_store"
    assert evidence.storage_owner == "storage.evidence_store"


def test_business_discovery_has_no_parallel_truth_store_or_domain_registry() -> None:
    forbidden_class_names = {
        "BusinessGoalRegistry",
        "BusinessConstraintRegistry",
        "BusinessProfileStore",
        "BusinessTruthStore",
        "DiscoveryStore",
        "DiscoveryRepository",
        "EvidenceStore",
        "WorldModel",
        "WorldModelStore",
    }
    discovered: dict[str, str] = {}

    for path in _discovery_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in forbidden_class_names:
                discovered[node.name] = str(path.relative_to(ROOT))

    assert discovered == {}


def test_owner_assertion_ingress_uses_existing_fact_evidence_and_state_owners() -> None:
    source = (DISCOVERY_ROOT / "ingress.py").read_text(encoding="utf-8")

    assert "EventFactLifecycleWriter" in source
    assert "EvidenceStore" in source
    assert "StateSynthesisEngine" in source
    assert "StateSynthesisRequest" in source
    assert "class BusinessProfileStore" not in source
    assert "class DiscoveryStore" not in source
    assert "class WorldModel" not in source


def test_business_discovery_http_route_is_projection_only() -> None:
    route = (ROOT / "adapters/api/fastapi/business_workspace_discovery_routes.py").read_text(
        encoding="utf-8"
    )
    assert "business_owner_scope" in route
    assert "BusinessDiscoveryWorkspace" in route
    assert "EventFactLifecycleWriter" not in route
    assert "EvidenceStore" not in route
    assert "StateSynthesisEngine" not in route


def test_legacy_onboarding_python_authority_is_retired_after_canonical_migration() -> None:
    legacy_root = ROOT / "core" / "autopilot" / "onboarding"
    assert (legacy_root / "README.md").exists()
    assert tuple(legacy_root.glob("*.py")) == ()

    migration = DISCOVERY_ROOT / "workspace.py"
    source = migration.read_text(encoding="utf-8")
    assert "OwnerBusinessAssertionIngress" in source
    assert "OwnerBusinessAssertion(" in source
    assert "class DiscoveryStore" not in source
    assert "class BusinessProfileStore" not in source


def test_legacy_onboarding_migration_is_wired_into_authenticated_production_workspace() -> None:
    router = (ROOT / "adapters" / "api" / "fastapi" / "router_adapter.py").read_text(
        encoding="utf-8"
    )
    route = (
        ROOT / "adapters" / "api" / "fastapi" / "business_workspace_discovery_routes.py"
    ).read_text(encoding="utf-8")

    assert "LegacyOnboardingEventReader" in router
    assert "LegacyOnboardingMigrator" in router
    assert "legacy_onboarding_reader=LegacyOnboardingEventReader(" in router
    assert "legacy_onboarding_migrator=LegacyOnboardingMigrator(" in router
    assert "actor_id=_actor_id(principal)" in route
