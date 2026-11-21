"""Only verified roles can use business capabilities; executor re-checks."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.users.roles import cockpit_permission, effective_role, has_permission, permissions_for
from core.ux.unified_messenger_menu import menu_items
from runtime.handler_impl.domains import business_flow_ops as ops


def _ctx(roles=(), is_admin=False):
    return SimpleNamespace(roles=list(roles), is_admin=is_admin,
                           settings={"user:role": "owner"})


def test_settings_cannot_claim_owner_role():
    assert effective_role(is_platform_admin=False, roles=[]) == "guest"
    assert not has_permission(_ctx(), "payments")
    assert has_permission(_ctx(["owner"]), "payments")
    assert not has_permission(_ctx(["operator"]), "customers")
    assert has_permission(_ctx(["marketer"]), "marketing")
    assert has_permission(_ctx(is_admin=True), "administration")
    assert not has_permission(_ctx(["owner"]), "administration")


def test_menu_and_cockpit_have_shared_permissions():
    assert [item.key for item in menu_items(role="guest")] == ["connect"]
    assert "payments" in [item.key for item in menu_items(role="owner")]
    for callback, required in (
        ("cpm:customers", "customers"), ("cpm:growth", "marketing"),
        ("cpm:growth-an:7", "analytics"), ("cpm:money", "payments"),
        ("cpm:calendar", "operations"),
    ):
        assert cockpit_permission(callback) == required
        assert required in permissions_for(is_platform_admin=False, roles=["owner"])


@pytest.mark.parametrize(("roles", "expected"), [
    (set(), False), ({"operator"}, False), ({"marketer"}, False),
    ({"owner"}, True), ({"admin"}, True),
])
def test_cockpit_authorization_uses_event_roles(monkeypatch, roles, expected):
    calls = []
    monkeypatch.setattr("core.admin.roles_read_model.roles_for_user",
                        lambda store, *, tenant_id, user_id: roles)
    monkeypatch.setattr("runtime.platform.config.env_flags.env_csv", lambda name: [])
    assert ops._actor_permits({"user_id": "user-1"}, event_store=object(),
                              tenant_id="tenant-1", permission="payments") is expected
    assert calls == []
