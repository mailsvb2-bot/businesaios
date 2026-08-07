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
    assert all(token in app for token in ("/public-site/integrations", "/public-site/cta/start", "/web/provider-tokens", "Ключи и токены вводятся только в защищённом control-plane"))
    assert all(token not in app for token in ("/control-plane/provider-admin/activate", "providerSecrets", "secret_fields"))


def test_frontend_styles_cover_onboarding_integrations_autonomy_and_workspace() -> None:
    styles = _read("styles.css")
    assert all(selector in styles for selector in (".onboarding-shell", ".stepper", ".integration-grid", ".autonomy-grid", ".workspace-grid", ".progress-card"))
