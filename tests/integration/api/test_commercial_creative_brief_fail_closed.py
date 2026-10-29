"""Fail-closed validation before entering the canonical advertising scene agent."""
from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
import pytest

from adapters.api.fastapi import business_workspace_commercial_routes as routes
from core.growth.ads.creative import pipeline


@pytest.mark.parametrize("headline,description", [
    ("", "description"),
    ("   ", "description"),
    (None, "description"),
    (123, "description"),
    ("headline", ""),
    ("headline", "   "),
    ("headline", None),
    ("headline", ["not text"]),
])
def test_malformed_creative_brief_rejected_before_llm(monkeypatch, headline, description):
    monkeypatch.setattr(routes, "business_owner_scope",
                        lambda **kw: ("owner", "tenant-test", "business-test"))
    monkeypatch.setattr(pipeline, "visual_scene_breakdown",
                        lambda *args, **kwargs: pytest.fail("LLM invoked for invalid brief"))

    router = APIRouter()
    routes.register_business_workspace_commercial_routes(
        router=router, auth_bundle=object(), purchases=object(),
        scene_agent=object(),
    )
    app = FastAPI()
    app.include_router(router)
    valid = dict(
        campaign_id="campaign-test", headline=headline, description=description,
        brand_context="Brand", campaign_goal="awareness",
        kind="image", formats=["square"],
    )
    with TestClient(app) as client:
        response = client.post(
            "/business-workspace/commercial/advertising/creatives/prepare",
            json=valid,
        )
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "advertising_brief_invalid"
