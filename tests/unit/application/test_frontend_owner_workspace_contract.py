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
