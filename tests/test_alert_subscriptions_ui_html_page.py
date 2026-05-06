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
