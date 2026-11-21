"""Admin analytics must verify durable authorization at executor boundary."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime.handler_impl.domains import business_flow_ops as ops


@pytest.mark.parametrize(("roles", "allowed"), [
    (set(), False), ({"operator"}, False), ({"admin"}, True),
])
def test_executor_analytics_checks_roles(monkeypatch, roles, allowed):
    observed = []
    monkeypatch.setattr("core.admin.roles_read_model.roles_for_user",
                        lambda store, *, tenant_id, user_id: roles)
    monkeypatch.setattr("runtime.platform.config.env_flags.env_csv", lambda name: [])
    monkeypatch.setattr(ops, "render_admin_analytics",
                        lambda **kwargs: observed.append(kwargs) or "real report")
    monkeypatch.setattr(ops, "send_tracked",
                        lambda body, effects, env, **kwargs: kwargs)
    env = SimpleNamespace(decision=SimpleNamespace())
    result = ops.handle_business_ops_summary(
        {"tenant_id": "tenant-1", "user_id": "u1",
         "op": "admin_analytics", "arg": "admin:segments"},
        object(), env, event_store=object(), now_ms=123,
    )
    assert bool(observed) == allowed
    if allowed:
        assert result["text"] == "real report"
        assert observed[0]["tenant_id"] == "tenant-1"
    else:
        assert result["ok"] is False
        assert result["reason"] == "forbidden"


def test_unknown_admin_report_denied_even_with_admin_role(monkeypatch):
    monkeypatch.setattr("core.admin.roles_read_model.roles_for_user",
                        lambda *args, **kwargs: {"admin"})
    monkeypatch.setattr("runtime.platform.config.env_flags.env_csv", lambda name: [])
    monkeypatch.setattr(ops, "send_tracked",
                        lambda body, effects, env, **kwargs: kwargs)
    result = ops.handle_business_ops_summary(
        {"tenant_id": "tenant-1", "user_id": "u1",
         "op": "admin_analytics", "arg": "admin:secret"},
        object(), SimpleNamespace(), event_store=object(), now_ms=123,
    )
    assert result["ok"] is False
