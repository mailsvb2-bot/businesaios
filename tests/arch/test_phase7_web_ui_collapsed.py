from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAGES = PROJECT_ROOT / "app" / "web" / "pages"

LEGACY_WRAPPERS = {
    "autopilot.py",
    "campaigns.py",
    "connectors.py",
    "dashboard.py",
    "leads.py",
    "marketplace.py",
    "notifications.py",
    "onboarding.py",
    "page_builders.py",
    "platforms.py",
    "revenue.py",
    "seo.py",
    "settings.py",
}

REQUIRED_OWNER_PAGES = {
    "__init__.py",
    "admin.py",
    "analytics.py",
    "approvals.py",
    "audit.py",
    "client_outcomes.py",
    "connector_admin.py",
    "inference_capacity.py",
    "inference_runtime_admin.py",
    "platform_control_center.py",
    "policy_overrides.py",
    "provider_tokens_admin.py",
    "queue_history.py",
    "queue_ops.py",
    "runtime_alerts.py",
    "security.py",
    "tenants.py",
}


def test_legacy_marketing_page_wrappers_do_not_regrow() -> None:
    py_files = {p.name for p in PAGES.glob("*.py")}
    assert py_files.isdisjoint(LEGACY_WRAPPERS)


def test_current_admin_owner_page_wrappers_remain() -> None:
    py_files = {p.name for p in PAGES.glob("*.py")}
    assert REQUIRED_OWNER_PAGES.issubset(py_files)


def test_demand_pages_live_in_separate_subpackage() -> None:
    demand = PAGES / "demand"
    assert demand.exists()
    assert (demand / "__init__.py").exists()
