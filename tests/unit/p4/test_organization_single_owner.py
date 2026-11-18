from types import SimpleNamespace

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from adapters.api.fastapi import public_site_routes as routes
from application.organization.registry import OrganizationRegistry, business_organization
from application.public_site.cta_intake import CTALandingIntakeService
from reliability.idempotency_store import InMemoryIdempotencyStore
from tests.unit.application.test_organization_registry import MemoryEventStore


@pytest.fixture
def setup(monkeypatch, tmp_path):
    monkeypatch.setenv("BAI_ORGANIZATION_NAME_CANONICAL_ENABLED", "1")
    monkeypatch.setenv("BAI_UNIFIED_ORGANIZATION_SETTINGS_ENABLED", "1")
    service = CTALandingIntakeService(storage_path=str(tmp_path / "intake.jsonl"))
    initial = service.submit(payload={"business_name": "Студия", "industry": "services"}, owner_account_id="owner")
    events = MemoryEventStore()
    registry = OrganizationRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore())
    monkeypatch.setattr(routes, "CTALandingIntakeService", lambda: service)
    monkeypatch.setattr(routes, "business_owner_scope",
                        lambda **_: (SimpleNamespace(actor_id="owner"), initial.tenant_id, initial.business_id))
    router = APIRouter()
    routes.register_public_site_routes(
        router=router, enforce_public_security=lambda **_: None, organization_registry=registry)
    app = FastAPI()
    app.include_router(router)
    return SimpleNamespace(http=TestClient(app), registry=registry, service=service,
                           tenant=initial.tenant_id, business=initial.business_id, events=events)


def test_read_has_no_migration_side_effect_and_default_off(setup, monkeypatch):
    response = setup.http.get("/business-workspace/settings")
    assert response.status_code == 200
    assert response.json()["name_source"] == "intake_pending_migration"
    assert not setup.events.events
    monkeypatch.setenv("BAI_ORGANIZATION_NAME_CANONICAL_ENABLED", "0")
    assert "name_source" not in setup.http.get("/business-workspace/settings").json()
    assert not setup.events.events


def test_name_migrates_once_without_overwriting_intake(setup):
    before = setup.http.get("/business-workspace/settings").json()
    payload = {"business_name": "Студия Плюс", "activity_description": "Йога",
               "timezone_name": "Europe/Moscow", "expected_revision": before["revision"]}
    headers = {"X-Idempotency-Key": "save-1"}
    response = setup.http.post("/business-workspace/settings", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["business_name"] == "Студия Плюс" and saved["organization_updated_at_ms"] is not None
    assert setup.service.read_business_settings(tenant_id=setup.tenant, business_id=setup.business)["business_name"] == "Студия"
    org = business_organization(setup.registry, tenant_id=setup.tenant, business_id=setup.business)
    assert org.name == "Студия Плюс"
    count = len(setup.events.events)
    assert setup.http.get("/business-workspace/settings").json()["business_name"] == "Студия Плюс"
    assert len(setup.events.events) == count
    assert setup.http.post("/business-workspace/settings", json=payload, headers=headers).status_code == 200
    assert len(setup.events.events) == count


def test_stale_revision_denied_without_any_write(setup):
    first = setup.http.post("/business-workspace/settings", json={
        "business_name": "Студия Плюс", "activity_description": "",
        "timezone_name": "Europe/Moscow", "expected_revision": 0,
    }, headers={"X-Idempotency-Key": "s-1"})
    assert first.status_code == 200, first.text
    revision = first.json()["organization_updated_at_ms"]
    setup.registry.update(tenant_id=setup.tenant, business_id=setup.business,
                          organization_id=setup.business, idempotency_key="other-editor", name="Из Telegram")
    original_intake_revision = setup.service.read_business_settings(tenant_id=setup.tenant,
                                                                   business_id=setup.business)["revision"]
    denied = setup.http.post("/business-workspace/settings", json={
        "business_name": "Из веба", "activity_description": "",
        "timezone_name": "Europe/Moscow", "expected_revision": original_intake_revision,
        "expected_organization_updated_at_ms": revision,
    }, headers={"X-Idempotency-Key": "s-2"})
    assert denied.status_code == 409
    assert setup.service.read_business_settings(tenant_id=setup.tenant,
                                                business_id=setup.business)["revision"] == original_intake_revision


def test_flag_off_keeps_legacy_settings_payload(setup, monkeypatch):
    monkeypatch.setenv("BAI_ORGANIZATION_NAME_CANONICAL_ENABLED", "0")
    response = setup.http.post("/business-workspace/settings", json={
        "business_name": "Новый", "activity_description": "",
        "timezone_name": "Europe/Moscow", "expected_revision": 0,
    }, headers={"X-Idempotency-Key": "old-1"})
    assert response.status_code == 200, response.text
    assert setup.service.read_business_settings(tenant_id=setup.tenant, business_id=setup.business)["business_name"] == "Новый"
    assert business_organization(setup.registry, tenant_id=setup.tenant, business_id=setup.business) is None
