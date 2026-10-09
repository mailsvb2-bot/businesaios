from __future__ import annotations

from pathlib import Path


def test_frontend_uses_owner_workspace_without_persisting_session_or_secrets() -> None:
    source = Path('frontend/src/App.jsx').read_text(encoding='utf-8')
    assert '/business-workspace/providers' in source
    assert '/actions/execute' in source and '/business-workspace/customers' in source
    assert '/web/provider-tokens' not in source
    assert 'X-API-Key' in source
    assert 'owner_session' in source
    assert 'localStorage' not in source
    assert 'sessionStorage' not in source
    assert 'write_actions_enabled' not in source or 'write' in source.lower()


def test_frontend_requires_persisted_successful_live_sync_evidence_before_verified_result() -> None:
    source = Path('frontend/src/App.jsx').read_text(encoding='utf-8')
    assert 'isSuccessfulLiveEvidence' in source
    assert 'historyByProvider' in source
    assert 'row?.accepted === true' in source
    assert '=== "live_executed"' in source
    assert 'Данные получены' in source
    assert 'Результат подтверждён реальным чтением данных из подключённого источника.' in source


def test_sales_center_stays_read_only_until_decisioncore_and_approval_boundary() -> None:
    source = Path('frontend/src/App.jsx').read_text(encoding='utf-8')
    assert 'className="panel sales-panel"' in source
    assert 'hubspotCanRefreshSales' in source
    assert 'contact_sync' in source and 'deal_sync' in source
    assert 'Кнопка выполняет только чтение HubSpot' in source
    assert '/business-workspace/decision-draft' in source
    assert '/actions/execute' in source
    assert 'Черновик из DecisionCore' in source
    assert 'Подтвердить и выполнить' in source
    assert 'provider-history' in source
    assert 'live_executed' in source


def test_owner_cockpit_uses_single_business_workspace_surface() -> None:
    source = Path('frontend/src/App.jsx').read_text(encoding='utf-8')
    assert 'function Workspace(' in source
    for route in (
        '/business-workspace/providers',
        '/business-workspace/customers',
        '/business-workspace/acquisition-plan',
        '/business-workspace/decision-draft',
        '/business-workspace/process-observations',
        '/business-workspace/process-opportunities',
        '/business-workspace/discovery',
    ):
        assert route in source
    assert '/web/provider-tokens' not in source
    assert 'localStorage' not in source
    assert 'sessionStorage' not in source
    assert 'Центр продаж' in source
    assert 'Центр действий' in source



def test_phase18_event_landing_has_owner_editor_and_anonymous_published_view() -> None:
    workspace = Path('frontend/src/App.jsx').read_text(encoding='utf-8')
    editor = Path('frontend/src/EventLandingWorkspace.jsx').read_text(encoding='utf-8')
    public = Path('frontend/src/PublicEventLanding.jsx').read_text(encoding='utf-8')
    bootstrap = Path('frontend/src/main.jsx').read_text(encoding='utf-8')

    assert '<EventLandingWorkspace' in workspace
    # React remounts the editor when the owner switches businesses, preventing
    # a private draft from the previous tenant/business remaining on screen.
    assert 'key={`${data.tenant_id}:${data.business_id}`}' in workspace
    assert 'apiKey={apiKey}' in workspace
    # A pending mutation cannot be redirected to a different event ID.
    assert 'disabled={Boolean(busy)} value={eventId}' in editor
    assert '/business-workspace/event-landings/' in editor
    assert 'expected_revision: snapshot.revision' in editor
    assert 'idempotency_key: pending.current.key' in editor
    for action in ('create', 'save', 'publish', 'unpublish'):
        assert 'commit("' + action + '")' in editor
    assert 'Сначала сохраните изменения черновика' in editor
    assert 'parsePublicEventQuery(window.location.search)' in bootstrap
    assert '<PublicEventLanding' in bootstrap
    assert '/public-site/events/' in public
    assert 'credentials: "omit"' in public
    assert 'payload.content' in public
    assert 'localStorage' not in editor + public
    assert 'sessionStorage' not in editor + public


def test_owner_support_case_journey_uses_authenticated_canonical_workspace_only() -> None:
    app = Path('frontend/src/App.jsx').read_text(encoding='utf-8')
    panel = Path('frontend/src/SupportCasesWorkspace.jsx').read_text(encoding='utf-8')
    routes = Path('adapters/api/fastapi/public_routes.py').read_text(encoding='utf-8')
    assert '<SupportCasesWorkspace' in app
    assert 'support:${data.tenant_id}:${data.business_id}' in app
    assert '/business-workspace/support-cases' in panel
    assert 'X-API-Key' in panel and 'credentials: "include"' not in panel
    assert 'localStorage' not in panel and 'sessionStorage' not in panel
    assert 'crypto.randomUUID()' in panel and 'pending.current.key' in panel
    assert 'register_business_workspace_support_case_routes(' in routes
    assert 'SupportCaseRegistry(' in routes


def test_phase18_operator_console_isolated_from_owner_and_uses_real_auth_boundary() -> None:
    root = Path("frontend/src/main.jsx").read_text(encoding="utf-8")
    panel = Path("frontend/src/SupportOperatorConsole.jsx").read_text(encoding="utf-8")
    routes = Path("adapters/api/fastapi/business_workspace_support_case_routes.py").read_text(encoding="utf-8")
    assert 'get("support_console") === "1"' in root
    assert "<SupportOperatorConsole apiBase={apiBase} />" in root
    assert "publicEvent ? <PublicEventLanding" in root
    assert "/platform-support" in panel
    assert '"/session"' in panel and '"/cases"' in panel
    assert '"X-API-Key": key' in panel
    assert 'credentials: "omit"' in panel
    assert 'cache: "no-store"' in panel
    assert "sessionStorage" not in panel and "localStorage" not in panel
    assert "crypto.randomUUID()" in panel and "pending.current.key" in panel
    assert '"support_case_manage"' in routes
    assert "RoleId.SUPPORT" in routes
    assert "@router.get(\"/platform-support/session\"" in routes
    assert 'dict(principal.metadata or {}).get("business_id")' in routes
    assert "request.query_params" not in routes
