from __future__ import annotations

import ast
from pathlib import Path

from application.campaign.projector import CANON_CAMPAIGN_PROJECTOR
from application.campaign.registry import CANON_CAMPAIGN_LIFECYCLE_OWNER
from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = Path("application/campaign/registry.py")
PROJECTOR = Path("application/campaign/projector.py")
FACT_TYPES = {"campaign.created", "campaign.updated", "campaign.archived"}


def _python_files():
    for root_name in ("application", "runtime", "storage", "core", "adapters", "billing", "crm"):
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_campaign_inventory_names_one_writer_and_projection() -> None:
    row = ontology_ownership_by_entity()["Campaign"]
    assert CANON_CAMPAIGN_LIFECYCLE_OWNER is True
    assert CANON_CAMPAIGN_PROJECTOR is True
    assert row.status is OwnershipAuditStatus.DONE
    assert row.allowed_writers == ("application.campaign.registry",)
    assert row.allowed_readers == ("application.campaign.projector",)


def test_campaign_lifecycle_owner_marker_is_unique() -> None:
    owners = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "CANON_CAMPAIGN_LIFECYCLE_OWNER"
                for target in node.targets
            ) and isinstance(node.value, ast.Constant) and node.value.value is True:
                owners.append(path.relative_to(ROOT))
    assert owners == [REGISTRY]


def test_campaign_fact_vocabulary_has_one_owner() -> None:
    owners: set[Path] = set()
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in FACT_TYPES:
                owners.add(path.relative_to(ROOT))
    assert owners == {PROJECTOR}


def test_ads_campaign_dto_and_builders_are_not_lifecycle_owners() -> None:
    for relative in (
        "interfaces/ads/base.py",
        "core/growth/campaign_builder.py",
        "core/traffic/contracts.py",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "CANON_CAMPAIGN_LIFECYCLE_OWNER" not in text


def test_business_autonomy_wires_campaign_to_existing_event_store() -> None:
    wiring = (ROOT / "runtime/business_autonomy/ontology_runtime.py").read_text(encoding="utf-8")
    assert "CampaignRegistry(event_store=event_store, idempotency_store=idempotency_store)" in wiring
    assert '"_campaign_registry"' in wiring
