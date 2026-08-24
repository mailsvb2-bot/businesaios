from pathlib import Path


APP = Path(__file__).resolve().parents[3] / "frontend" / "src" / "App.jsx"


def test_provider_readiness_is_tracked_per_provider_without_global_state_bleed() -> None:
    app = APP.read_text(encoding="utf-8")

    assert "const liveEvidenceByProvider = useMemo(() =>" in app
    assert "const activeLiveEvidence = activeProvider ? liveEvidenceByProvider.get(activeProvider.provider_key) || null : null;" in app
    assert 'liveEvidence?.provider_key === activeProvider.provider_key' not in app
    assert 'liveEvidenceByProvider.has(item.provider_key) ? "Данные получены"' in app
    assert '"Доступ сохранён · данные ещё не получены"' in app
    assert 'className={activeLiveEvidence ? "done" : activeProvider.connected ? "active" : ""}' in app


def test_connected_without_read_and_verified_read_have_distinct_user_actions() -> None:
    app = APP.read_text(encoding="utf-8")

    assert "Доступ к источнику сохранён" in app
    assert "Получить первые реальные данные" in app
    assert "Первые данные из этого источника подтверждены" in app
    assert "Обновить данные" in app
    assert 'if (name === "sync" || name === "probe") await loadHistory(providerKey);' in app
