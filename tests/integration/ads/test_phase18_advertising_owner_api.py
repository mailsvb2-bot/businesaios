"""Owner advertising API must return only scoped, unlaunched creative drafts."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.api.fastapi import business_workspace_commercial_routes as module


@pytest.mark.parametrize("kind", ["image", "video"])
def test_owner_advertising_prepare_requires_scope_and_never_spends(monkeypatch, kind):
    def authorize(*, request, auth_bundle):
        assert request.headers.get("x-api-key") == "owner-key"
        return ("owner-1", "tenant-one", "business-one")

    monkeypatch.setattr(module, "business_owner_scope", authorize)
    app = FastAPI()
    from fastapi import APIRouter
    router = APIRouter()
    module.register_business_workspace_commercial_routes(
        router=router, auth_bundle=object(), purchases=object(),
    )
    app.include_router(router)
    response = TestClient(app).post(
        "/business-workspace/commercial/advertising/creatives/prepare",
        headers={"X-API-Key": "owner-key"},
        json={"campaign_id": "campaign-1", "headline": "Consultation",
              "description": "Book a meeting", "brand_context": "Blue brand",
              "campaign_goal": "Appointments", "kind": kind,
              "formats": ["square", "story"]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["tenant_id"] == "tenant-one"
    assert payload["business_id"] == "business-one"
    assert payload["draft_only"] is True
    assert payload["generation_submitted"] is False
    assert payload["campaign_launched"] is False
    assert payload["spend_authorized"] is False
    assert len(payload["creatives"]) == 3
    assert all(x["kind"] == kind and x["tenant_id"] == "tenant-one" for x in payload["creatives"])


def test_owner_advertising_rejects_extra_provider_controls(monkeypatch):
    monkeypatch.setattr(module, "business_owner_scope", lambda **kwargs: ("owner", "tenant", "business"))
    from fastapi import APIRouter
    router = APIRouter()
    module.register_business_workspace_commercial_routes(router=router, auth_bundle=None, purchases=None)
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).post(
        "/business-workspace/commercial/advertising/creatives/prepare",
        json={"campaign_id": "campaign", "headline": "Name", "description": "Text",
              "brand_context": "Brand", "campaign_goal": "Leads",
              "kind": "image", "formats": ["square"], "launch": True},
    )
    assert response.status_code == 422


def test_owner_advertising_prepare_uses_art_director_with_safe_rule_fallback(monkeypatch):
    from types import SimpleNamespace

    from fastapi import APIRouter

    monkeypatch.setattr(module, "business_owner_scope", lambda **kwargs: ("owner", "tenant", "business"))
    calls = []

    class Agent:
        def run_task(self, task, ctx):
            calls.append((task.value, ctx.tenant_id, ctx.offer["request"]))
            return SimpleNamespace(json={"subject": "диван", "action": "мастер чистит диван"}, text="")

    body = {"campaign_id": "c", "headline": "Химчистка", "description": "Чистим диваны",
            "brand_context": "Бренд", "campaign_goal": "Заявки", "kind": "image", "formats": ["square"]}
    for agent, expected in ((Agent(), "мастер чистит диван"), (None, None)):
        router = APIRouter()
        module.register_business_workspace_commercial_routes(
            router=router, auth_bundle=None, purchases=None, scene_agent=agent,
        )
        app = FastAPI()
        app.include_router(router)
        response = TestClient(app).post("/business-workspace/commercial/advertising/creatives/prepare", json=body)
        assert response.status_code == 200, response.text
        creatives = response.json()["creatives"]
        direction = dict(creatives[0]["visual_direction"])
        assert direction.get("action") == expected and direction["subject"]
    assert calls == [("ads.visual.scene", "tenant", "Химчистка. Чистим диваны")]
