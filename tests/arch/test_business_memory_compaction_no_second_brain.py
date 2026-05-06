from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "execution" / "business_memory_policy.py"
COMPACTOR_PATH = ROOT / "execution" / "business_memory_compactor.py"
STORE_PATH = ROOT / "execution" / "business_operating_memory.py"
UPDATER_PATH = ROOT / "execution" / "world_state_updater.py"


FORBIDDEN_MARKERS = (
    "DecisionCore",
    "execute_action",
    "ActionExecutor",
    "RuntimeDecisionCore",
    "closed_loop_orchestrator",
    "goal_decomposition_engine",
    "long_horizon_planner",
)


def test_business_memory_compaction_modules_do_not_import_decision_surfaces() -> None:
    for path in (POLICY_PATH, COMPACTOR_PATH):
        text = path.read_text(encoding="utf-8")
        for marker in FORBIDDEN_MARKERS:
            assert marker not in text, f"{path.name} must remain evidence-only and must not reference {marker}."


def test_business_operating_memory_reexports_single_execution_owners() -> None:
    text = STORE_PATH.read_text(encoding="utf-8")
    assert "from execution.business_memory_policy import BusinessMemoryPolicy" in text
    assert "from execution.business_memory_compactor import BusinessMemoryCompactor" in text
    assert text.count("class BusinessMemoryPolicy") == 0
    assert text.count("class BusinessMemoryCompactor") == 0


def test_business_memory_store_keeps_compaction_inside_execution_memory_boundary() -> None:
    text = STORE_PATH.read_text(encoding="utf-8")
    assert "business_memory_query" not in text
    assert "business_memory_state_adapter" not in text
    assert "runtime.platform.business_memory.service" not in text
    assert "runtime.platform.business_memory.store" not in text


def test_world_state_updater_stays_feedback_only_without_decision_paths() -> None:
    text = UPDATER_PATH.read_text(encoding="utf-8")
    for marker in FORBIDDEN_MARKERS:
        assert marker not in text, f"world_state_updater must not reference {marker}."


def test_execution_query_and_state_adapter_reuse_canonical_memory_projection() -> None:
    query_text = (ROOT / "execution" / "business_memory_query.py").read_text(encoding="utf-8")
    adapter_text = (ROOT / "execution" / "business_memory_state_adapter.py").read_text(encoding="utf-8")
    assert "project_business_memory_contract_bundle" in query_text
    assert "project_business_memory_contract_bundle" in adapter_text
    assert "project_business_memory_meta_payloads" in adapter_text
    assert "meta.update(meta_payloads)" in adapter_text


def test_state_adapter_uses_canonical_memory_rehydration_before_projection() -> None:
    adapter_text = (ROOT / "execution" / "business_memory_state_adapter.py").read_text(encoding="utf-8")
    assert "canonicalize_business_memory_payload" in adapter_text


def test_state_adapter_reuses_canonical_state_projection_surface() -> None:
    adapter_text = (ROOT / "execution" / "business_memory_state_adapter.py").read_text(encoding="utf-8")
    assert "project_business_memory_state_context" in adapter_text


def test_execution_memory_exports_shared_projection_helpers() -> None:
    store_text = STORE_PATH.read_text(encoding="utf-8")
    assert "def canonicalize_business_memory_payload(" in store_text
    assert "def project_business_memory_evidence(" in store_text
    assert "def project_business_memory_summary(" in store_text
    assert "def project_business_memory_governance_summary(" in store_text
    assert "def project_business_memory_patterns(" in store_text
    assert "def project_business_memory_profile(" in store_text
    assert "def project_business_memory_recent_runs(" in store_text
    assert "def project_business_memory_state_context(" in store_text
    assert "def project_business_memory_contract_bundle(" in store_text
    assert "def project_business_memory_meta_payloads(" in store_text


def test_headless_and_opportunity_surfaces_reuse_canonical_business_memory_helpers() -> None:
    mapper_text = (ROOT / "application" / "headless" / "goal_mapper.py").read_text(encoding="utf-8")
    detector_text = (ROOT / "execution" / "opportunity_detector.py").read_text(encoding="utf-8")
    persistence_text = (ROOT / "execution" / "evidence_feedback_state.py").read_text(encoding="utf-8")
    assembly_text = (ROOT / "application" / "autonomy" / "autonomy_state_assembly.py").read_text(encoding="utf-8")
    assert "project_business_memory_evidence" in mapper_text
    assert "project_business_memory_profile" in mapper_text
    assert "project_business_memory_state_context" in detector_text
    assert "project_business_memory_evidence" in persistence_text
    assert "project_business_memory_contract_bundle" in assembly_text
    assert "project_business_memory_meta_payloads" in assembly_text
    assert "meta.update(meta_payloads)" in assembly_text


def test_headless_feedback_uses_canonical_business_memory_projection() -> None:
    feedback_text = (ROOT / "application" / "headless" / "feedback.py").read_text(encoding="utf-8")
    assert "project_business_memory_contract_bundle" in feedback_text
    assert "project_business_memory_feedback_snapshot" in feedback_text



def test_governance_and_persistence_surfaces_reuse_canonical_governance_summary() -> None:
    governance_text = (ROOT / "execution" / "governance_service.py").read_text(encoding="utf-8")
    evidence_text = (ROOT / "execution" / "canonical_governance_evidence.py").read_text(encoding="utf-8")
    persistence_text = (ROOT / "execution" / "evidence_feedback_state.py").read_text(encoding="utf-8")
    assert "project_business_memory_governance_summary" in governance_text
    assert "project_business_memory_governance_summary" in evidence_text
    assert "project_business_memory_governance_summary" in persistence_text


def test_owner_path_reuses_canonical_business_memory_summary_for_state_synthesis() -> None:
    owner_path_text = (ROOT / "execution" / "owner_path" / "owner_path_service.py").read_text(encoding="utf-8")
    assert "project_business_memory_governance_summary" in owner_path_text
    assert "business_memory_summary" in owner_path_text


def test_execution_memory_exports_feedback_snapshot_helper() -> None:
    store_text = STORE_PATH.read_text(encoding="utf-8")
    assert "def project_business_memory_feedback_snapshot(" in store_text


def test_meta_surfaces_reuse_canonical_business_memory_meta_payloads() -> None:
    adapter_text = Path("execution/business_memory_state_adapter.py").read_text(encoding="utf-8")
    assembly_text = Path("application/autonomy/autonomy_state_assembly.py").read_text(encoding="utf-8")
    assert "project_business_memory_meta_payloads" in adapter_text
    assert "project_business_memory_meta_payloads" in assembly_text



def test_governance_and_promotion_helpers_reuse_canonical_governance_summary() -> None:
    governance_gate_text = (ROOT / "execution" / "business_memory_governance.py").read_text(encoding="utf-8")
    promotion_text = (ROOT / "execution" / "business_memory_promotion.py").read_text(encoding="utf-8")
    assert "project_business_memory_governance_summary" in governance_gate_text
    assert "project_business_memory_governance_summary" in promotion_text
