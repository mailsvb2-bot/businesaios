from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_frontend_is_self_service_product_workspace_not_staging_console() -> None:
    app = (REPO_ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")

    assert "BusinessAIOS Control UI" not in app
    assert "Staging UI" not in app
    assert "Создать рабочее пространство" in app
    assert "Подключите сервисы, которыми уже пользуетесь" in app
    assert "Первый результат" in app
    assert "Советник" in app
    assert "Помощник" in app
    assert "Автопилот" in app


def test_frontend_uses_existing_safe_provider_admin_contract() -> None:
    app = (REPO_ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")

    assert "/public-site/cta/start" in app
    assert "/control-plane/provider-admin/catalog" in app
    assert "/control-plane/provider-admin/activate" in app
    assert 'requested_surface: "self_service_business_workspace"' in app
    assert 'probe_mode: "dry_run"' in app
    assert 'autonomy_tier: "supervised"' in app
    assert "Подключить и проверить" in app


def test_frontend_styles_cover_onboarding_integrations_and_autonomy_modes() -> None:
    styles = (REPO_ROOT / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")

    assert ".onboarding-shell" in styles
    assert ".provider-grid" in styles
    assert ".provider-card" in styles
    assert ".mode-grid" in styles
    assert ".modal-backdrop" in styles
