import ast
from pathlib import Path


def test_evidence_persistence_delegates_world_state_projection_to_owner() -> None:
    text = Path("application/evidence/evidence_persistence.py").read_text(encoding="utf-8")
    module = ast.parse(text)
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "application.evidence.evidence_feedback_state"
        and any(
            alias.name == "apply_feedback_to_world_state"
            and alias.asname == "_apply_feedback_world_state"
            for alias in node.names
        )
        for node in module.body
    )
    assert "project_business_memory_evidence" not in text
    assert "project_business_memory_governance_summary" not in text
    assert "return _apply_feedback_world_state(" in text


def test_evidence_feedback_state_owns_business_memory_projection() -> None:
    text = Path("application/evidence/evidence_feedback_state.py").read_text(encoding="utf-8")
    assert "project_business_memory_evidence" in text
    assert "project_business_memory_governance_summary" in text
    assert "def apply_feedback_to_world_state(" in text



def test_headless_boot_reuses_canonical_event_store_for_outcome_chronology() -> None:
    boot = Path("execution/headless_boot.py").read_text(encoding="utf-8")
    contract = Path("application/headless/contract.py").read_text(encoding="utf-8")
    persistence = Path("application/evidence/evidence_persistence.py").read_text(
        encoding="utf-8"
    )

    assert "del event_store" not in boot
    assert "event_store=event_store" in boot
    assert "event_store: Any | None = None" in contract
    assert "resolved_event_store = event_store" in contract
    assert "event_store=resolved_event_store" in contract
    assert "BusinessOutcomeEventSpineProjector" in persistence



def test_business_outcome_event_spine_projection_has_one_non_authoritative_owner() -> None:
    roots = (
        Path("application"),
        Path("execution"),
        Path("runtime"),
        Path("storage"),
    )
    marker = "CANON_BUSINESS_OUTCOME_EVENT_SPINE_PROJECTION = True"
    owners = [
        path
        for root in roots
        if root.exists()
        for path in root.rglob("*.py")
        if marker in path.read_text(encoding="utf-8")
    ]

    assert owners == [Path("application/outcome/evidence_projection.py")]
    text = owners[0].read_text(encoding="utf-8")
    assert "BusinessFactV1(" not in text
    assert "append_event" in text
