from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import APIRouter, HTTPException

from adapters.api.fastapi import business_workspace_event_landing_routes as owner_routes
from adapters.api.fastapi.public_site_routes import register_public_site_routes
from application.public_site.landing_content import EventLandingState
from contracts.landing_page import EventLandingContent, EventLandingFaq


def _content(title: str) -> EventLandingContent:
    return EventLandingContent(
        eyebrow="Онлайн", hero_title=title, hero_subtitle="Подзаголовок",
        audience_title="Для кого", audience_points=("Владельцы",), outcomes_title="Результат",
        outcome_points=("Польза",), agenda_title="Программа", agenda_points=("Шаг",),
        speaker_title="Спикер", speaker_text="Команда", faq_title="FAQ",
        faq=(EventLandingFaq(question="Когда?", answer="Сегодня."),), cta_title="Регистрация", cta_text="Оставьте данные.",
    )


def _endpoint(router: APIRouter, path: str, method: str):
    return next(r.endpoint for r in router.routes if getattr(r, "path", None)==path and method in getattr(r, "methods", set()))


class _Registry:
    def __init__(self, state): self.state=state; self.calls=[]
    def get(self, **kwargs): self.calls.append(("get",kwargs)); return self.state
    def create(self, **kwargs): self.calls.append(("create",kwargs)); return self.state
    def transition(self, **kwargs): self.calls.append(("transition",kwargs)); return self.state


def test_public_event_route_never_exposes_unpublished_draft() -> None:
    state=EventLandingState(event_id="event-1",draft=_content("Secret"),draft_source="manual")
    registry=_Registry(state); router=APIRouter()
    register_public_site_routes(router=router,enforce_public_security=lambda **_: None,event_landing_registry=registry)
    endpoint=_endpoint(router,"/public-site/events/{tenant_id}/{business_id}/{event_id}","GET")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint("tenant-a","business-a","event-1",object()))
    assert (exc.value.status_code,exc.value.detail)==(404,"event_landing_not_published")


def test_public_event_route_returns_exact_published_snapshot() -> None:
    state=EventLandingState(event_id="event-1",draft=_content("Public"),draft_source="manual").publish(expected_revision=1)
    registry=_Registry(state); router=APIRouter()
    register_public_site_routes(router=router,enforce_public_security=lambda **_: None,event_landing_registry=registry)
    endpoint=_endpoint(router,"/public-site/events/{tenant_id}/{business_id}/{event_id}","GET")
    result=asyncio.run(endpoint("tenant-a","business-a","event-1",object()))
    assert result["content"]["hero_title"]=="Public"
    assert result["revision"]==1


def test_owner_event_route_uses_authenticated_scope_not_body(monkeypatch) -> None:
    state=EventLandingState(event_id="event-1",draft=_content("Draft"),draft_source="manual")
    registry=_Registry(state); router=APIRouter()
    monkeypatch.setattr(owner_routes,"business_owner_scope",lambda **_: (SimpleNamespace(actor_id="owner",subject="owner"),"tenant-session","business-session"))
    owner_routes.register_business_workspace_event_landing_routes(router=router,auth_bundle=object(),event_landing_registry=registry)
    async def body(_):
        return {"action":"create","content":_content("Draft").to_payload(),"idempotency_key":"create-1"}
    monkeypatch.setattr(owner_routes,"json_body",body)
    endpoint=_endpoint(router,"/business-workspace/event-landings/{event_id}","POST")
    asyncio.run(endpoint("event-1",object()))
    call=registry.calls[-1][1]
    assert (call["tenant_id"],call["business_id"])==("tenant-session","business-session")



def test_owner_event_duplicate_create_returns_conflict_not_server_error(monkeypatch) -> None:
    class _ExistingRegistry(_Registry):
        def create(self, **kwargs):
            raise RuntimeError("event_landing_already_exists")

    state = EventLandingState(event_id="event-1", draft=_content("Draft"), draft_source="manual")
    router = APIRouter()
    monkeypatch.setattr(
        owner_routes, "business_owner_scope",
        lambda **_: (SimpleNamespace(actor_id="owner", subject="owner"), "tenant-a", "business-a"),
    )
    owner_routes.register_business_workspace_event_landing_routes(
        router=router, auth_bundle=object(), event_landing_registry=_ExistingRegistry(state),
    )

    async def body(_):
        return {
            "action": "create",
            "content": _content("Conflicting landing").to_payload(),
            "idempotency_key": "new-owner-request",
        }

    monkeypatch.setattr(owner_routes, "json_body", body)
    endpoint = _endpoint(router, "/business-workspace/event-landings/{event_id}", "POST")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint("event-1", object()))
    assert (exc.value.status_code, exc.value.detail) == (409, "event_landing_already_exists")
