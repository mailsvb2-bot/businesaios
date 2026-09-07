from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "frontend" / "src"


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_owner_workspace_connects_existing_analytics_memory_and_decisioncore() -> None:
    app = _read("App.jsx")
    panel = _read("BusinessIntelligencePanel.jsx")
    assert 'BusinessIntelligencePanel' in app
    assert '/analytics/dashboard/' in app
    assert '/business-memory/summary' in app
    assert '/business-memory/recent-runs' in app
    assert '/goals/execute' in app
    assert 'key={data.business_id}' in app
    assert 'Promise.allSettled' in app
    assert all(token in panel for token in ("Что происходит и что делать дальше", "Что BusinessAIOS помнит", "Дайте системе цель обычными словами"))


def test_intelligence_reads_canonical_owners_without_creating_second_brain() -> None:
    app = _read("App.jsx")
    panel = _read("BusinessIntelligencePanel.jsx")
    assert 'analytics.value?.payload' in app
    assert 'recent.value?.runs' in app
    assert 'Отдельной памяти, второй аналитики или обходного исполнителя кабинет не создаёт.' in panel
    assert all(token not in app + panel for token in ("localStorage", "sessionStorage", "indexedDB.open", "new EventStore", "new Scheduler"))


def test_goal_surface_is_advisory_replay_protected_and_never_requests_external_execution() -> None:
    app = _read("App.jsx")
    panel = _read("BusinessIntelligencePanel.jsx")
    assert '"X-Idempotency-Key": crypto.randomUUID()' in app
    assert 'max_steps: 1' in app
    assert 'meta: { source: "owner_workspace" }' in app
    # Safety tier is server-owned; the browser must not be able to relax it.
    assert 'autonomy_tier' not in app
    assert "Ничего внешнему сервису не отправлено." in panel
    assert "Эта кнопка не выполняет внешние действия." in panel
    assert "Остановлено правилами безопасности" in panel
    assert "режиме анализа и плана" in panel


def test_intelligence_failure_is_isolated_from_rest_of_owner_workspace() -> None:
    app = _read("App.jsx")
    panel = _read("BusinessIntelligencePanel.jsx")
    assert 'Promise.allSettled' in app
    assert 'errors: [analytics, memory, recent]' in app
    assert "Остальные функции кабинета продолжают работать." in panel
    assert "Часть данных сейчас недоступна" in panel


def test_intelligence_surface_is_responsive_and_accessible() -> None:
    panel = _read("BusinessIntelligencePanel.jsx")
    styles = _read("BusinessIntelligencePanel.css")
    assert 'aria-labelledby="business-intelligence-title"' in panel
    assert 'aria-label="Ключевые показатели бизнеса"' in panel
    assert panel.count('role="alert"') >= 2
    assert 'role="status"' in panel
    assert all(selector in styles for selector in (".intelligence-panel", ".intelligence-metrics", ".intelligence-columns", ".intelligence-goal-card", "@media (max-width: 480px)"))
