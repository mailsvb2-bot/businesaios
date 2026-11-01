from scripts.server import smoke_flow


def test_production_smoke_uses_tenant_scoped_control_plane(monkeypatch):
    monkeypatch.setenv("CONTROL_PLANE_API_KEY", "test-service-key")
    monkeypatch.setenv("SMOKE_TENANT_ID", "tenant-live")
    calls = []

    def fake_fetch(url, *, method, headers, payload, timeout, follow_redirects):
        calls.append((url, method, dict(headers)))
        if url.endswith("/health"):
            return 200, {"status": "ok"}
        if url.endswith("/readyz"):
            return 200, {"status": "ready"}
        if url.endswith("/control-plane/admin/tenant-policy/tenant-live"):
            return 200, {"tenant_id": "tenant-live", "policy": {}}
        if url.endswith("/actions/execute"):
            return 200, {"status": "accepted"}
        if url.endswith("/control-plane/audit/actions"):
            return 200, {"records": [{"action_id": calls[-2][2]["x-action-id"]}]}
        raise AssertionError(f"unexpected smoke endpoint: {url}")

    monkeypatch.setattr(smoke_flow, "fetch_json", fake_fetch)
    result = smoke_flow.run_smoke_flow()
    assert result["tenant_id"] == "tenant-live"
    assert any("/tenant-policy/tenant-live" in url for url, _, _ in calls)
    assert not any("/admin/tenants" in url for url, _, _ in calls)
