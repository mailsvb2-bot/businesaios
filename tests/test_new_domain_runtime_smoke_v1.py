from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.economics.contracts import UnitEconomicsSnapshot
from core.finance.builders.cashflow_builder import build_cashflow_snapshot
from core.governance.contracts import AuditRecord
from core.knowledge.enums import SourceKind
from core.knowledge.types import LessonDraft, MemoryRetrieval, TagSet
from core.learning_loop.types import LearningBatch
from core.product.contracts import ProductFeature
from core.simulation.contracts import ScenarioOutcome
from runtime.boot.knowledge_boot import build_knowledge_services
from runtime.handlers.economics_explain import handle_economics_explain
from runtime.handlers.finance_explain import handle_finance_explain
from runtime.handlers.governance_explain import handle_governance_explain
from runtime.handlers.human_governance_explain import handle_human_governance_explain
from runtime.handlers.learning_loop_build import handle_learning_loop_build
from runtime.handlers.product_build import handle_product_build
from runtime.handlers.simulation_explain import handle_simulation_explain
from runtime.human_governance import build_runtime_review_case
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def test_product_runtime_smoke() -> None:
    proposal = handle_product_build(ProductFeature(feature_id="f1", name="x", impact_score=0.9))
    assert proposal.feature_id == "f1"


def test_learning_loop_runtime_smoke() -> None:
    proposal = handle_learning_loop_build(LearningBatch(batch_id="b1", sample_count=10))
    assert proposal.reason.startswith("batch:")


def test_economics_explain_runtime_smoke() -> None:
    text = handle_economics_explain(UnitEconomicsSnapshot(tenant_id="t1", cac=1.0, ltv=2.0, margin=3.0))
    assert "cac=1.0" in text


def test_finance_explain_runtime_smoke() -> None:
    text = handle_finance_explain(build_cashflow_snapshot(tenant_id="t1", revenue=10.0, expenses=4.0))
    assert "cashflow=6.0" in text


def test_governance_explain_runtime_smoke() -> None:
    text = handle_governance_explain(AuditRecord(decision_id="d1", risk_score=0.2, status="ok"))
    assert "decision_id=d1" in text


def test_human_governance_explain_runtime_smoke() -> None:
    text = handle_human_governance_explain(build_runtime_review_case(subject_id="s1", reason="manual"))
    assert "review:s1" in text


def test_knowledge_explain_runtime_smoke() -> None:
    bundle = build_knowledge_services(event_store=MemoryEventStore(), tenant_id="tenant-a")
    bundle.command_service.record_lesson(
        LessonDraft(
            subject="topic",
            title="Memory lesson title",
            narrative="Memory lesson narrative",
            source_kind=SourceKind.MANUAL,
            source_ref="manual-1",
            tags=TagSet.from_iterable(["topic"]),
            observed_at=datetime.now(tz=UTC) - timedelta(days=1),
            created_by="tester",
            evidence_refs=("ev-1",),
        )
    )
    text = bundle.explain_service.explain_retrieval(
        MemoryRetrieval(
            target_subject="topic",
            task="explain memory",
            tags=TagSet.from_iterable(["topic"]),
            now=datetime.now(tz=UTC),
        )
    )
    assert "Memory trace explanation" in text


def test_simulation_explain_runtime_smoke() -> None:
    text = handle_simulation_explain(ScenarioOutcome(tenant_id="t1", scenario_name="baseline", confidence=0.3, downside_risk=0.1))
    assert "scenario=baseline" in text
