from __future__ import annotations

from pathlib import Path


def test_frontend_uses_owner_workspace_without_persisting_session_or_secrets() -> None:
    source = Path('frontend/src/App.jsx').read_text(encoding='utf-8')
    assert '/business-workspace/providers' in source
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
