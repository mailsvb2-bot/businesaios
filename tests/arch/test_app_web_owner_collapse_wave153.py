from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding='utf-8')


def test_app_web_package_roots_are_owner_surfaces() -> None:
    components = _read('app/web/components/__init__.py')
    assert 'Canonical web components package surface' in components
    assert 'install_public_api_alias(__name__)' in components
    assert not (ROOT / 'app/web/components/public_api/__init__.py').exists()

    pages = _read('app/web/pages/__init__.py')
    assert 'Canonical web pages package surface' in pages
    assert 'install_public_api_alias(__name__)' in pages
    assert not (ROOT / 'app/web/pages/public_api/__init__.py').exists()


def test_page_modules_prefer_component_package_root() -> None:
    relpaths = [
        'app/web/pages/admin.py',
        'app/web/pages/approvals.py',
        'app/web/pages/audit.py',
        'app/web/pages/policy_overrides.py',
        'app/web/pages/queue_history.py',
        'app/web/pages/queue_ops.py',
        'app/web/pages/runtime_alerts.py',
        'app/web/pages/security.py',
        'app/web/pages/tenants.py',
    ]
    for relpath in relpaths:
        content = _read(relpath)
        assert 'from app.web.components import ' in content, relpath
        assert '.public_api import' not in content, relpath


def test_removed_web_wrapper_modules_do_not_regrow() -> None:
    removed = [
        'app/web/components/autopilot_button.py',
        'app/web/components/campaign_status_card.py',
        'app/web/components/connector_health_card.py',
        'app/web/components/decision_feed.py',
        'app/web/components/growth_summary_card.py',
        'app/web/components/lead_feed.py',
        'app/web/components/magic_moment_banner.py',
        'app/web/components/onboarding_checklist.py',
        'app/web/components/revenue_card.py',
        'app/web/components/component_builders.py',
        'app/web/pages/autopilot.py',
        'app/web/pages/dashboard.py',
        'app/web/pages/campaigns.py',
        'app/web/pages/connectors.py',
        'app/web/pages/leads.py',
        'app/web/pages/marketplace.py',
        'app/web/pages/notifications.py',
        'app/web/pages/onboarding.py',
        'app/web/pages/page_builders.py',
        'app/web/pages/platforms.py',
        'app/web/pages/revenue.py',
        'app/web/pages/seo.py',
        'app/web/pages/settings.py',
        'app/web/public_api/__init__.py',
        'app/web/components/public_api/__init__.py',
        'app/web/pages/public_api/__init__.py',
        'app/web/components/demand/public_api/__init__.py',
        'app/web/pages/demand/public_api/__init__.py',
    ]
    for relpath in removed:
        assert not (ROOT / relpath).exists(), relpath
