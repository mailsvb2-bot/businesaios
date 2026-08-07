from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_frontend_is_self_service_product_workspace_not_staging_console() -> None:
    app = (REPO_ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")

    assert "BusinessAIOS Control UI" not in app
    assert "Staging UI" not in app
    assert "Подключите бизнес" in app
    assert "Где уже живут данные бизнеса?" in app
    assert "Первый полезный результат" in app
    assert "Советник" in app
    assert "Помощник" in app
    assert "Автопилот" in app


def test_public_frontend_uses_truth_marketplace_and_never_collects_provider_secrets() -> None:
    app = (REPO_ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")

    assert "/public-site/integrations" in app
    assert "/public-site/cta/start" in app
    assert "/web/provider-tokens" in app
    assert "/control-plane/provider-admin/activate" not in app
    assert "providerSecrets" not in app
    assert "secret_fields" not in app
    assert "Ключи и токены вводятся только в защищённом control-plane" in app


def test_frontend_styles_cover_onboarding_integrations_autonomy_and_workspace() -> None:
    styles = (REPO_ROOT / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")

    assert ".onboarding-shell" in styles
    assert ".stepper" in styles
    assert ".integration-grid" in styles
    assert ".autonomy-grid" in styles
    assert ".workspace-grid" in styles
    assert ".progress-card" in styles
