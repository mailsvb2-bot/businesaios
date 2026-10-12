"""Canonical targeted-domain CI must own commercial journeys, without extra workflows."""
from __future__ import annotations

from pathlib import Path

from scripts.ci import targeted_domain_ci as targeted
from scripts.ci.config import project_shape_config
from scripts.ci.step_project_shape import run as assert_project_shape


COMMERCIAL_JOURNEY_FILES = (
    "tests/integration/api/test_phase18_commercial_ingress_journey.py",
    "tests/integration/api/test_phase18_commercial_context_journey.py",
    "tests/integration/api/test_phase18_commercial_order_journey.py",
    "tests/integration/api/test_phase18_commercial_checkout_journey.py",
    "tests/integration/api/test_phase18_commercial_owner_http.py",
    "tests/integration/api/test_phase18_commercial_settlement_journey.py",
    "tests/integration/api/test_phase18_paid_program_access_journey.py",
    "tests/integration/api/test_phase18_program_enrollment_canonical_customer.py",
    "tests/integration/api/test_phase18_program_publication_journey.py",
)
CANONICAL_TOUCH_POINTS = (
    "application/commerce/phase18_commercial_order.py",
    "application/commerce/phase18_program_publication_registry.py",
    "application/lead/registry.py",
    "billing/phase18_commercial_settlement.py",
    "billing/invoice_registry.py",
    "runtime/business_autonomy/provider_inbound_webhook_service.py",
    "runtime/messaging/conversation_registry.py",
    "adapters/api/fastapi/business_workspace_commercial_routes.py",
    "adapters/api/fastapi/business_workspace_program_routes.py",
    "frontend/src/CommercialSalesWorkspace.jsx",
    "tests/integration/api/test_phase18_commercial_settlement_journey.py",
)


def test_commercial_acceptance_suites_are_selected_by_every_critical_owner(monkeypatch):
    monkeypatch.setattr(
        targeted, "git_lines",
        lambda *args: list(COMMERCIAL_JOURNEY_FILES)
        if args == ("ls-files", "tests/**/*.py") else [],
    )
    for changed in CANONICAL_TOUCH_POINTS:
        domains = targeted.touched_domains([changed])
        assert "commercial_journey" in domains, changed
        selected = set(targeted.matching_tests(domains))
        assert set(COMMERCIAL_JOURNEY_FILES).issubset(selected), (changed, selected)


def test_commercial_evidence_lives_under_one_approved_workflow_set():
    root = Path(__file__).resolve().parents[2]
    config = project_shape_config(root)
    actual = tuple(sorted(
        path.relative_to(root).as_posix()
        for path in (root / ".github/workflows").glob("*.yml")
    ))
    assert actual == tuple(sorted(config.allowed_workflows))
    assert "commercial_journey" in targeted.DOMAIN_KEYWORDS
    assert assert_project_shape() == (True, "project shape contract satisfied")
