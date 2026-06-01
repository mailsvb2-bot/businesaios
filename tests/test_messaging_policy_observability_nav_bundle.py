from runtime.boot.web.runtime_web_service_builders import build_messaging_policy_observability_nav_bundle


def test_nav_bundle_serves_json_and_html():
    bundle = build_messaging_policy_observability_nav_bundle()
    j = bundle.json(tenant_id="t1")
    h = bundle.html(tenant_id="t1")
    assert j.status_code == 200
    assert j.body["tenant_id"] == "t1"
    assert len(j.body["items"]) >= 5
    assert h.status_code == 200
    assert "Messaging Policy Observability" in h.body
    assert "tenant_id" in h.body
