"""Chat text is deterministically routed without a second LLM decision owner."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.policies.telegram.routes.command_routes import classify_free_text


def _ctx(text, roles=(), is_admin=False):
    return SimpleNamespace(text=text, cmd=None, callback_data=None,
                           roles=list(roles), is_admin=is_admin)


@pytest.mark.parametrize(("text", "roles", "admin", "kind"), [
    ("хочу увеличить продажи", ["owner"], False, "business_goal"),
    ("Как поднять средний чек?", [], True, "business_goal"),
    ("хочу увеличить продажи", ["operator"], False, "none"),
    ("Здравствуйте, вы работаете в субботу?", [], False, "customer_message"),
    ("Хочу купить тариф, мой телефон +7 999 123-45-67", [], False, "lead"),
    ("меню", [], False, "owner_command"),
    ("статус", ["owner"], False, "owner_command"),
    ("привет", ["owner"], False, "none"),
])
def test_free_text_classification(text, roles, admin, kind):
    assert classify_free_text(_ctx(text, roles, admin)) == kind


def test_owner_goals_use_analytics_permission():
    from core.users.roles import cockpit_permission, permissions_for

    assert cockpit_permission("cpm:growth-now") == "analytics"
    assert "analytics" in permissions_for(is_platform_admin=False, roles=["owner"])
    assert "analytics" not in permissions_for(is_platform_admin=False, roles=["operator"])
