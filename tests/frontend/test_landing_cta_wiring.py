from pathlib import Path


def test_frontend_onboarding_is_wired_to_truthful_public_api() -> None:
    app = Path("frontend/src/App.jsx").read_text(encoding="utf-8")
    assert "/public-site/integrations" in app
    assert "/public-site/cta/start" in app
    assert "finishOnboarding" in app
    assert "selected_providers: selectedProviders" in app
    assert "/business-workspace/providers" in app
    assert "/web/provider-tokens" not in app
    assert "/control-plane/provider-admin/activate" not in app


def test_frontend_product_onboarding_controls_are_styled() -> None:
    styles = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    for selector in (".onboarding-shell", ".stepper", ".integration-grid", ".autonomy-grid", ".workspace-grid"):
        assert selector in styles
