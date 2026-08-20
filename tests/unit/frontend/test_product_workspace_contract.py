from pathlib import Path


ROOT = Path(__file__).resolve().parents[3] / "frontend" / "src"


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_frontend_is_self_service_product_workspace_not_staging_console() -> None:
    app = _read("App.jsx")
    assert all(token not in app for token in ("BusinessAIOS Control UI", "Staging UI"))
    assert all(token in app for token in ("Подключите бизнес", "Где уже живут данные бизнеса?", "Первый полезный результат", "Советник", "Помощник", "Автопилот"))


def test_public_frontend_uses_truth_marketplace_and_never_collects_provider_secrets() -> None:
    app = _read("App.jsx")
    assert all(token in app for token in ("/public-site/integrations", "/public-site/cta/start", "/business-workspace/providers", "/business-workspace/acquisition-plan", "Данные входа не сохраняются в браузере"))
    assert all(token not in app for token in ("/web/provider-tokens", "/control-plane/provider-admin/activate", "providerSecrets"))


def test_frontend_styles_cover_onboarding_integrations_autonomy_and_workspace() -> None:
    styles = _read("styles.css")
    assert all(selector in styles for selector in (".onboarding-shell", ".stepper", ".integration-grid", ".autonomy-grid", ".workspace-grid", ".progress-card"))


def test_owner_workspace_uses_plain_business_language_for_first_value() -> None:
    app = _read("App.jsx")
    planner = _read("AcquisitionPlanner.jsx")
    visible_copy = app + "\n" + planner
    assert all(token in visible_copy for token in ("Безопасный режим · только чтение", "Получить первые данные", "Данные получены", "Уточнить расчёт вручную"))
    assert all(token.lower() not in visible_copy.lower() for token in ("OWNER-сесс", "tenant-bound", "provider runtime", "sync evidence", "read-only sync", "Статус truth", "Write-действия"))


def test_owner_workspace_exposes_simple_first_value_acquisition_planner_without_losing_full_model() -> None:
    app = _read("App.jsx")
    planner = _read("AcquisitionPlanner.jsx")
    model = _read("acquisitionPlannerModel.js")
    styles = _read("AcquisitionPlanner.css")
    assert 'AcquisitionPlanner enabled={Boolean(apiKey)}' in app
    assert all(token in planner for token in ("Быстрый расчёт", "Сколько клиентов можно получить с вашим бюджетом?", "Уточнить расчёт вручную", "Рассчитать", "не подтверждённые показатели бизнеса", "Стоимость клиента", "Ценность / стоимость", "Окупаемость"))
    assert planner.count("setResult(null);") >= 2
    assert all(token in planner for token in ("const valid = isAcquisitionFormValid(form)", "disabled={!enabled || busy || !valid}", "if (!valid)", "daily_budget: Number(form.target_days) > 0 ? Number(form.total_budget) / Number(form.target_days) : 0"))
    assert 'export const ACQUISITION_PRIMARY_FIELDS' in model and 'export const ACQUISITION_ADVANCED_FIELDS' in model
    assert '["conversion_percent", "Конверсия лид → клиент, %", "Ваше текущее или ожидаемое значение", 0.01, 100, 0.01]' in model
    assert all(token in model for token in ("target_customers", "total_budget", "daily_budget", "target_days", "cost_per_entry", "gross_margin_ltv", "expected_monthly_margin_per_customer", "conversion_rate: Number(form.conversion_percent) / 100", "isAcquisitionFormValid", "String(raw).trim() === \"\"", "Number.isFinite(value)", "Math.abs(steps - Math.round(steps)) < 1e-8"))
    assert all(token in styles for token in (".planner-shell", ".planner-form", ".planner-metrics", ".planner-advanced-block", "@media (max-width: 560px)"))
    assert "Финансовые выводы появятся после подключения реальных данных" in app
