from __future__ import annotations

from pathlib import Path

from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity

ROOT = Path(__file__).resolve().parents[2]


def test_action_inventory_names_existing_evidence_owner() -> None:
    row = ontology_ownership_by_entity()["Action"]
    assert row.status is OwnershipAuditStatus.DONE
    assert row.authoritative_module == "contracts.action_intent"
    assert row.storage_owner == "storage.evidence_store"
    assert row.allowed_writers == ("application.evidence.evidence_persistence",)
    assert row.allowed_readers == ("application.action.evidence_projection",)
    assert "lineage-only Evidence rows" in row.reason
    assert "legacy history" in row.reason


def test_original_action_intent_is_handed_to_feedback_without_reconstruction() -> None:
    loop = (ROOT / "application/autonomy/autonomy_loop.py").read_text(encoding="utf-8")
    feedback = (ROOT / "application/autonomy/autonomy_feedback_step.py").read_text(encoding="utf-8")
    assert "action_intent=decision.action_intent" in loop
    assert 'feedback["action_intent"] = action_intent.as_dict()' in feedback


def test_action_intent_full_body_uses_canonical_evidence_writer_and_read_only_projector() -> None:
    persistence = (ROOT / "application/evidence/evidence_persistence.py").read_text(encoding="utf-8")
    projection = (ROOT / "application/action/evidence_projection.py").read_text(encoding="utf-8")
    assert "'action_intent': action_intent" in persistence
    assert "EvidenceStore" in projection
    assert "self._evidence.append(" not in projection
    assert "ActionIntentV1.from_projection(" in projection
    assert "legacy_incomplete_count" in projection
    assert 'not _mapping(record.payload.get("action_intent"))' in projection


def test_action_intent_contract_has_one_json_safe_body_projection() -> None:
    contract = (ROOT / "contracts/action_intent.py").read_text(encoding="utf-8")
    assert "def as_dict(self)" in contract
    assert '"payload": self.payload_copy()' in contract
    assert '"evidence_refs": list(self.evidence_refs)' in contract
