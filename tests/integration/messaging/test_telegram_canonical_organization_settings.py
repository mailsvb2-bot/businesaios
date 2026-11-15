"""Organization Telegram journey uses one lifecycle owner and survives reopen."""
from __future__ import annotations

from types import SimpleNamespace

from application.organization import OrganizationRegistry
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from core.policies.telegram.routes.settings_routes import handle_settings_routes
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.handler_impl.domains.business_catalog_ops import organization_card


class Events:
    def __init__(self):
        self.events = []

    def append_event(self, event):
        self.events.append(dict(event))

    def iter_events(self, *, tenant_id, start_ms=0, event_type=None, **kwargs):
        return (dict(e) for e in self.events if e.get("tenant_id") == tenant_id
                and int(e.get("timestamp_ms", 0)) >= start_ms
                and (event_type is None or e.get("event_type") == event_type))


def test_organization_create_update_readback_no_second_registry():
    events = Events()
    owner = OrganizationRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore())
    args = dict(registry=owner, tenant_id="t1", business_id="b1", user_id="admin")
    text, _ = organization_card(**args, operation="organization_show", arg="", decision_id="read")
    assert "не создана" in text
    text, _ = organization_card(**args, operation="organization_create",
                                arg="Студия развития | услуги", decision_id="create-1")
    assert "Студия развития" in text
    assert len(events.events) == 1
    assert events.events[0]["event_type"] == BUSINESS_FACT_EVENT_TYPE
    text, _ = organization_card(**args, operation="organization_name",
                                arg="Новая студия", decision_id="update-1")
    assert "Новая студия" in text
    assert len(events.events) == 2
    text, _ = organization_card(**args, operation="organization_show", arg="", decision_id="read-2")
    assert "Новая студия" in text
    text, _ = organization_card(**args, operation="organization_name",
                                arg="Новая студия", decision_id="new-user-action")
    assert "Новая студия" in text and len(events.events) == 2
    assert owner.list_for_business(tenant_id="t1", business_id="b1")[0].name == "Новая студия"
    assert owner.list_for_business(tenant_id="t1", business_id="b2") == ()


def test_organization_telegram_requires_admin_and_selected_business():
    def ctx(*, admin, session, cmd=None, callback=""):
        return SimpleNamespace(callback_data=callback, cmd=cmd, args="Новое название",
                               is_admin=admin, callback_query_id="callback-1",
                               state=SimpleNamespace(session=session))
    pm = lambda **kw: SimpleNamespace(action="send_message@v1", payload=kw)
    denied = handle_settings_routes(ctx(admin=False, session={"business_id": "b1"},
                                        callback="cp:settings:organization"),
                                    user_id="u", bot_username="", pm=pm)
    assert denied.action == "send_message@v1"
    missing = handle_settings_routes(ctx(admin=True, session={}, callback="cp:settings:organization"),
                                     user_id="u", bot_username="", pm=pm)
    assert missing.action == "send_message@v1"
    allowed = handle_settings_routes(ctx(admin=True, session={"selected_business_id": "b1"},
                                         callback="cp:settings:organization"),
                                     user_id="u", bot_username="", pm=pm)
    assert allowed.action == "business_admin@v1"
    assert allowed.payload["business_id"] == "b1"
    conflicting = handle_settings_routes(
        ctx(admin=True, session={"selected_business_id": "b1", "business_id": "b2"},
            callback="cp:settings:organization"),
        user_id="u", bot_username="", pm=pm,
    )
    assert conflicting.action == "send_message@v1"
    assert "Выберите бизнес заново" in conflicting.payload["text"]
    rename = handle_settings_routes(ctx(admin=True, session={"business_id": "b1"}, cmd="/org_name"),
                                    user_id="u", bot_username="", pm=pm)
    assert rename.payload["op"] == "organization_name" and rename.payload["arg"] == "Новое название"
