from __future__ import annotations

from app.web.routes import Routes


def test_default_routes_include_analytics_page() -> None:
    result = Routes().build_default(tenant_id="tenant-1")
    paths = {row["path"]: row["page"] for row in result["payload"]["routes"]}
    assert "/web/analytics" in paths
    assert paths["/web/analytics"] == "AnalyticsPage"
