from __future__ import annotations

from config.app_settings import AppSettings
from config.validation import validate_app_settings
from application.decision.action_result import ActionExecutionResult
from core.economics.capital_engine import AllocationPlan, CapitalPolicy
from core.knowledge.contracts import KnowledgeReadPort, KnowledgeWritePort
from core.learning_loop.service import DefaultLearningLoopService
from core.pricing.stop_loss import StopLossConfig, StopLossPolicy, StopLossWindow
from observability.structured_logging import StructuredLogger
from runtime.boot.governance import build_governance_service
from core.governance.types import PolicyState


def test_compat_shims_import_and_build() -> None:
    validate_app_settings(AppSettings(environment="dev"))
    assert ActionExecutionResult(status="ok", action_type="noop").status == "ok"
    logger = StructuredLogger("test.compat")
    logger.info("compat_ok", step="round4")
    svc = build_governance_service(policy_state=PolicyState(policy_name="default"))
    assert svc.policy_state().policy_name == "default"


def test_learning_loop_service_remains_advisory_only() -> None:
    payload = DefaultLearningLoopService().run(policy_id="p1", subject_id="s1")
    assert payload["status"] == "proposed"
    assert payload["proposal"]["confidence"] == 0.0


def test_pricing_stop_loss_compat_policy_surface() -> None:
    decision = StopLossPolicy(config=StopLossConfig(enabled=False), window=StopLossWindow(hours=24)).evaluate(
        event_store=object(),
        tenant_id="t1",
        offer_arm="base",
        candidate_price_rub=100,
        base_price_rub=100,
    )
    assert decision.allowed is True


def test_capital_policy_is_compat_advisory_wrapper() -> None:
    plan = AllocationPlan(allocations=[], horizon_days=30, expected_value=1.0, expected_risk=0.2, confidence=0.9)
    decision = CapitalPolicy(min_confidence=0.5, max_expected_risk=0.5).evaluate(plan)
    assert decision.approved is True


def test_knowledge_composite_ports_exist_for_legacy_imports() -> None:
    assert KnowledgeReadPort is not None
    assert KnowledgeWritePort is not None
