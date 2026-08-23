from pathlib import Path


ROOT = Path(__file__).resolve().parents[3] / "frontend" / "src"


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_frontend_is_self_service_product_workspace_not_staging_console() -> None:
    app = _read("App.jsx")
    assert all(token not in app for token in ("BusinessAIOS Control UI", "Staging UI"))
    assert all(token in app for token in ("Подключите бизнес", "Где уже живут данные бизнеса?", "Первый полезный результат", "Советник", "Помощник", "Автопилот"))


def test_public_frontend_uses_truth_marketplace_and_protected_provider_workspace() -> None:
    app = _read("App.jsx")
    assert all(token in app for token in ("/public-site/integrations", "/public-site/cta/start", "/business-workspace/providers", "/business-workspace/acquisition-plan", "не сохраняются в браузере"))
    assert all(token not in app for token in ("/web/provider-tokens", "/control-plane/provider-admin/activate", "providerSecrets"))


def test_frontend_styles_cover_onboarding_integrations_autonomy_workspace_and_first_value() -> None:
    styles = _read("styles.css")
    assert all(selector in styles for selector in (".onboarding-shell", ".stepper", ".integration-grid", ".autonomy-grid", ".workspace-grid", ".progress-card", ".first-value-panel", ".connection-steps"))


def test_owner_workspace_uses_plain_business_language_for_first_value() -> None:
    app = _read("App.jsx")
    planner = _read("AcquisitionPlanner.jsx")
    visible_copy = app + "\n" + planner
    assert all(token in visible_copy for token in ("Безопасный режим · чтение данных", "Получить первые данные", "Данные подтверждены", "Уточнить расчёт вручную"))
    assert all(token.lower() not in visible_copy.lower() for token in ("OWNER-сесс", "tenant-bound", "provider runtime", "sync evidence", "read-only sync", "Статус truth", "Write-действия"))


def test_owner_workspace_puts_verified_first_value_before_setup_and_keeps_one_clear_path() -> None:
    app = _read("App.jsx")
    styles = _read("styles.css")
    first_value = 'className="panel first-value-panel"'
    setup = 'className="workspace-grid"'
    assert first_value in app and setup in app
    assert app.index(first_value) < app.index(setup)
    assert all(token in app for token in ("Сначала факты — потом рекомендации", "1. Источник выбран", "2. Доступ", "3. Первые данные", "Подключить для чтения", "Получить первые данные"))
    assert "Аккаунт или ID" not in app
    assert all(selector in styles for selector in (".first-value-panel", ".result-badge.verified", ".compact-check-list", ".connection-flow", ".workspace-actions"))


def test_owner_workspace_resumes_server_session_without_persisting_owner_key_in_web_storage() -> None:
    app = _read("App.jsx")
    assert app.count('credentials: "include"') >= 2
    assert "localStorage.setItem" not in app
    assert "sessionStorage.setItem" not in app
    assert "indexedDB.open" not in app
    assert "Не удалось восстановить защищённый вход" in app
    assert "Вход в кабинет завершился после перезагрузки страницы" not in app


def test_owner_workspace_exposes_simple_first_value_acquisition_planner_without_losing_full_model() -> None:
    app = _read("App.jsx")
    planner = _read("AcquisitionPlanner.jsx")
    model = _read("acquisitionPlannerModel.js")
    styles = _read("AcquisitionPlanner.css")
    assert 'AcquisitionPlanner enabled={Boolean(apiKey)}' in app
    assert all(token in planner for token in ("Быстрый расчёт", "Сколько клиентов можно получить с вашим бюджетом?", "Уточнить расчёт вручную", "Рассчитать", "не подтверждённые показатели бизнеса", "Стоимость клиента", "Ценность / стоимость", "Окупаемость"))
    assert planner.count("setResult(null);") >= 2
    assert all(token in planner for token in ("const validationFields = showAdvanced ? ACQUISITION_FIELDS : ACQUISITION_PRIMARY_FIELDS", "const valid = isAcquisitionFormValid(form, validationFields)", "disabled={!enabled || busy || !valid}", "if (!valid)", "...ACQUISITION_DEFAULTS", "daily_budget: Number(form.target_days) > 0 ? Number(form.total_budget) / Number(form.target_days) : 0"))
    assert 'export const ACQUISITION_PRIMARY_FIELDS' in model and 'export const ACQUISITION_ADVANCED_FIELDS' in model
    assert '["conversion_percent", "Конверсия лид → клиент, %", "Ваше текущее или ожидаемое значение", 0.01, 100, 0.01]' in model
    assert all(token in model for token in ("target_customers", "total_budget", "daily_budget", "target_days", "cost_per_entry", "gross_margin_ltv", "expected_monthly_margin_per_customer", "conversion_rate: Number(form.conversion_percent) / 100", "isAcquisitionFormValid", "String(raw).trim() === \"\"", "Number.isFinite(value)", "Math.abs(steps - Math.round(steps)) < 1e-8", "fields = ACQUISITION_FIELDS"))
    assert all(token in styles for token in (".planner-shell", ".planner-form", ".planner-metrics", ".planner-advanced-block", "@media (max-width: 560px)"))
    assert "До первого чтения здесь нет финансовых обещаний" in app


def test_new_business_restart_clears_previous_onboarding_identity() -> None:
    app = _read("App.jsx")
    assert 'const INITIAL_FORM = {' in app
    assert 'const [form, setForm] = useState(() => ({ ...INITIAL_FORM }))' in app
    restart = app.split('const restart = () => {', 1)[1].split('if (result)', 1)[0]
    assert 'setStep(0)' in restart
    assert 'setSelectedProviders([])' in restart
    assert 'setForm({ ...INITIAL_FORM })' in restart
    assert 'setError("")' in restart


def test_mobile_workspace_keeps_safe_state_and_multiline_fields_styled() -> None:
    app = _read("App.jsx")
    styles = _read("styles.css")
    assert 'safe-chip-full' in app and 'safe-chip-short' in app
    assert 'Безопасный режим · чтение данных' in app and 'Режим чтения' in app and 'Только чтение' in app
    assert '.safe-chip-short { display: none; }' in styles
    assert '.safe-chip-full { display: none; }' in styles
    assert '.safe-chip-short { display: inline; }' in styles
    assert '@media (max-width: 420px)' in styles and '.brand-name { display: none; }' in styles
    assert 'button, input, select, textarea { font: inherit; }' in styles
    assert 'input, select, textarea {' in styles
    assert 'textarea { min-height: 112px;' in styles
    assert 'input:focus, select:focus, textarea:focus' in styles


def test_onboarding_validates_identity_and_recovers_integration_catalog_without_technical_jargon() -> None:
    app = _read("App.jsx")
    planner = _read("AcquisitionPlanner.jsx")
    styles = _read("styles.css")
    assert "function isValidEmail(value)" in app
    assert "if (step === 0) return Boolean(form.business_name.trim() && emailValid)" in app
    assert 'aria-invalid={Boolean(form.email.trim()) && !emailValid}' in app
    assert "Введите email в формате name@company.ru" in app
    assert "const [marketError, setMarketError] = useState" in app
    assert "const loadMarketplace = useCallback(async () =>" in app
    assert "void loadMarketplace()" in app
    assert "Повторить загрузку" in app and 'role="alert"' in app
    assert "Не удалось загрузить список интеграций. Проверьте соединение и повторите попытку." in app
    assert "Не удалось открыть защищённый список подключений. Проверьте соединение и повторите попытку." in app
    visible_copy = app + "\n" + planner
    assert "Проверьте API" not in visible_copy
    assert "ошибка API" not in visible_copy
    assert ".recovery-box" in styles and ".field-error" in styles


def test_workspace_accessibility_exposes_state_errors_focus_and_motion_preferences() -> None:
    app = _read("App.jsx")
    planner = _read("AcquisitionPlanner.jsx")
    styles = _read("styles.css")
    assert 'aria-current={index === step ? "step" : undefined}' in app
    assert 'aria-pressed={form.goal === goal.value}' in app
    assert 'aria-pressed={selected}' in app
    assert 'aria-pressed={form.autonomy_mode === mode.value}' in app
    assert 'aria-current={activeProvider?.provider_key === item.provider_key ? "true" : undefined}' in app
    assert 'role="progressbar"' in app and 'aria-valuenow={verifiedPercent}' in app
    assert 'aria-live="polite"' in app
    assert 'aria-describedby={form.email.trim() && !emailValid ? "owner-email-error" : undefined}' in app
    assert 'id="owner-email-error"' in app
    assert app.count('role="alert"') >= 4
    assert 'className="planner-error" role="alert"' in planner
    assert 'button:focus-visible, a:focus-visible, summary:focus-visible' in styles
    assert '@media (prefers-reduced-motion: reduce)' in styles
