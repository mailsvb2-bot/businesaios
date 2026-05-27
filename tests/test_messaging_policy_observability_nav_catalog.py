from interfaces.web.debug.messaging_policy_observability_nav.page_presenter import all_nav_items


def test_nav_catalog_contains_expected_pages():
    keys = {item.key for item in all_nav_items()}
    assert {"snapshot", "traces", "dashboard", "alerts", "alert_subscriptions"} <= keys
