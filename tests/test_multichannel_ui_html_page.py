from interfaces.web.settings.messaging_preferences.html_page import build_page


def test_build_page_includes_assets_and_endpoints():
    html = build_page(
        css_href="/static/channel_preferences.css",
        js_src="/static/channel_preferences.js",
        model_endpoint="/api/settings/messaging-preferences",
        save_endpoint="/api/settings/messaging-preferences",
    )
    assert "channel_preferences.css" in html
    assert "channel_preferences.js" in html
    assert "modelEndpoint" in html
    assert "saveEndpoint" in html
