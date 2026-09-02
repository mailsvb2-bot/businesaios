from pathlib import Path

from interfaces.web.settings.alert_subscriptions.html_page import build_page


def test_build_page_includes_assets_and_endpoints():
    html = build_page(
        css_href="/static/alert_subscriptions.css",
        js_src="/static/alert_subscriptions.js",
        model_endpoint="/api/settings/alert-subscriptions",
        save_endpoint="/api/settings/alert-subscriptions",
    )
    assert "alert_subscriptions.css" in html
    assert "alert_subscriptions.js" in html
    assert "modelEndpoint" in html
    assert "saveEndpoint" in html


def test_alert_subscriptions_client_preserves_business_scope():
    script = (Path(__file__).parents[1] / "interfaces/web/settings/alert_subscriptions/static/alert_subscriptions.js").read_text(encoding="utf-8")
    assert "Business id" in script
    assert 'business_id: item.business_id || ""' in script
    assert "Business id is required for Slack/Discord." in script
