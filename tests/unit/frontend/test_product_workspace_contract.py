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
    assert all(token in app for token in ("/public-site/integrations", "/public-site/cta/start", "/business-workspace/providers", "/business-workspace/acquisition-plan", "Ключ намеренно не сохраняется в браузере"))
    assert all(token not in app for token in ("/web/provider-tokens", "/control-plane/provider-admin/activate", "providerSecrets"))


def test_frontend_styles_cover_onboarding_integrations_autonomy_and_workspace() -> None:
    styles = _read("styles.css")
    assert all(selector in styles for selector in (".onboarding-shell", ".stepper", ".integration-grid", ".autonomy-grid", ".workspace-grid", ".progress-card"))


def test_owner_workspace_exposes_truthful_acquisition_scenario_planner() -> None:
    app = _read("App.jsx")
    planner = _read("AcquisitionPlanner.jsx")
    model = _read("acquisitionPlannerModel.js")
    styles = _read("AcquisitionPlanner.css")
    assert 'AcquisitionPlanner enabled={Boolean(apiKey)}' in app
    assert all(token in planner for token in ("Сценарий по вашим предположениям", "Проверить достижимость цели", "не подтверждённые показатели бизнеса", "CAC", "LTV/CAC", "Окупаемость"))
    assert planner.count("setResult(null);") >= 2
    assert all(token in planner for token in ("const valid = isAcquisitionFormValid(form)", "disabled={!enabled || busy || !valid}", "if (!valid)"))
    assert all(token in model for token in ("target_customers", "total_budget", "daily_budget", "target_days", "cost_per_entry", "gross_margin_ltv", "expected_monthly_margin_per_customer", "conversion_rate: Number(form.conversion_percent) / 100", "isAcquisitionFormValid", "String(raw).trim() === \"\"", "Number.isFinite(value)", "Math.abs(steps - Math.round(steps)) < 1e-8"))
    assert all(token in styles for token in (".planner-shell", ".planner-form", ".planner-metrics", "@media (max-width: 560px)"))
    assert "Фактические финансовые выводы появятся только после real sync" in app
