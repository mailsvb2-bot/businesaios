from __future__ import annotations

from types import SimpleNamespace

import pytest

from application.decision_runtime.flow import build_payload
from application.decision_state.state_world_model_enricher import (
    extract_actor_id,
    extract_product_metadata,
    extract_tenant_id,
)


def _state(
    *,
    tenant_id: str | None,
    product_id: str | None,
    actor_id: str | None = "owner-1",
) -> SimpleNamespace:
    product_metadata = {}
    if tenant_id is not None:
        product_metadata["tenant_id"] = tenant_id
    if product_id is not None:
        product_metadata.update(
            {
                "product_id": product_id,
                "domain": "crm",
                "product_version": "v7",
            }
        )
    return SimpleNamespace(
        tenant_id="default",
        user_id=actor_id or "",
        user={},
        product={},
        product_metadata=product_metadata,
        meta={},
        economy={},
    )


@pytest.mark.lock
def test_state_scope_and_actor_overwrite_conflicting_policy_before_signing() -> None:
    state = _state(tenant_id="business-a", product_id="crm-pro")
    _product_meta, product_id, domain, product_version = (
        extract_product_metadata(state)
    )
    tenant_id = extract_tenant_id(state)
    actor_id = extract_actor_id(state)
    out = SimpleNamespace(
        payload={
            "tenant_id": "business-b",
            "product_id": "wrong-product",
            "domain": "wrong-domain",
            "product_version": "wrong-version",
            "actor_id": "spoofed-actor",
            "admin_id": "spoofed-admin",
            "user_id": "target-user",
        }
    )

    _tagged, payload = build_payload(
        state=state,
        out=out,
        pinned_world_model_meta={},
        tenant_id=tenant_id,
        product_id=product_id,
        domain=domain,
        product_version=product_version,
        actor_id=actor_id,
    )

    assert payload["tenant_id"] == "business-a"
    assert payload["product_id"] == "crm-pro"
    assert payload["domain"] == "crm"
    assert payload["product_version"] == "v7"
    assert payload["actor_id"] == "owner-1"
    assert payload["admin_id"] == "owner-1"
    assert payload["user_id"] == "target-user"


@pytest.mark.lock
def test_placeholder_state_tenant_removes_policy_supplied_business() -> None:
    state = _state(tenant_id=None, product_id="crm-pro")
    _product_meta, product_id, domain, product_version = (
        extract_product_metadata(state)
    )
    tenant_id = extract_tenant_id(state)
    actor_id = extract_actor_id(state)
    out = SimpleNamespace(
        payload={
            "tenant_id": "policy-invented-business",
            "user_id": "target-user",
        }
    )

    _tagged, payload = build_payload(
        state=state,
        out=out,
        pinned_world_model_meta={},
        tenant_id=tenant_id,
        product_id=product_id,
        domain=domain,
        product_version=product_version,
        actor_id=actor_id,
    )

    assert tenant_id is None
    assert "tenant_id" not in payload
    assert payload["product_id"] == "crm-pro"
    assert payload["actor_id"] == "owner-1"


@pytest.mark.lock
def test_missing_state_actor_cannot_keep_policy_admin_identity() -> None:
    state = _state(
        tenant_id="business-a",
        product_id="crm-pro",
        actor_id=None,
    )
    _product_meta, product_id, domain, product_version = (
        extract_product_metadata(state)
    )
    out = SimpleNamespace(
        payload={
            "admin_id": "policy-admin",
            "actor_id": "policy-actor",
            "user_id": "target-user",
        }
    )

    _tagged, payload = build_payload(
        state=state,
        out=out,
        pinned_world_model_meta={},
        tenant_id=extract_tenant_id(state),
        product_id=product_id,
        domain=domain,
        product_version=product_version,
        actor_id=extract_actor_id(state),
    )

    assert "admin_id" not in payload
    assert "actor_id" not in payload
    assert payload["user_id"] == "target-user"
