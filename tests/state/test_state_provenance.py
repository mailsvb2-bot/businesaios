from __future__ import annotations

from runtime.state.state_contract import StateEvidenceRef, StateObservation
from runtime.state.state_provenance import merge_evidence_refs, provenance_hash


def test_state_provenance_hash_changes_when_value_changes() -> None:
    left = StateObservation(field_path="crm.lead_count", value=12, source="crm", observed_at_ms=1000)
    right = StateObservation(field_path="crm.lead_count", value=13, source="crm", observed_at_ms=1000)

    assert provenance_hash(observation=left) != provenance_hash(observation=right)


def test_state_provenance_evidence_is_deduplicated_and_stably_ordered() -> None:
    early = StateEvidenceRef(evidence_id="a", observed_at_ms=100)
    late = StateEvidenceRef(evidence_id="b", observed_at_ms=200)

    merged = merge_evidence_refs(left=(late, early), right=(early,))
    assert [item.evidence_id for item in merged] == ["a", "b"]
