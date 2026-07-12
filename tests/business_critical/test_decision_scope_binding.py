from __future__ import annotations

from types import SimpleNamespace

import pytest

from application.decision_runtime.flow import build_payload
from application.decision_state.state_world_model_enricher import (
    extract_product_metadata,
    extract_tenant_id,
)


def _state(*, tenant_id: str | None, product_id: str | None) -> SimpleNamespace:
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
        tenant_id="",
        product={},
        product_metadata=product_metadata,
        meta={},
        economy={},
    )


@pytest.mark.lock
def test_state_scope_overwrites_conflicting_policy_payload_before_signing() -> None:
    state = _state(tenant_id="business-a", product_id="crm-pro")
    _product_meta, product_id, domain, product_version = extract_product_metadata(state)
    tenant_id = extract_tenant_id(state)
    out = SimpleNamespace(
        payload={
            "tenant_id": "business-b",
            "product_id": "wrong-product",
            "domain": "wrong-domain",
            "product_version": "wrong-version",
            "user_id": "user-1",
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
    )

    assert payload["tenant_id"] == "business-a"
    assert payload["product_id"] == "crm-pro"
    assert payload["domain"] == "crm"
    assert payload["product_version"] == "v7"
    assert payload["user_id"] == "user-1"


@pytest.mark.lock
def test_missing_state_tenant_does_not_invent_default_business() -> None:
    state = _state(tenant_id=None, product_id="crm-pro")
    _product_meta, product_id, domain, product_version = extract_product_metadata(state)
    tenant_id = extract_tenant_id(state)
    out = SimpleNamespace(payload={"user_id": "user-1"})

    _tagged, payload = build_payload(
        state=state,
        out=out,
        pinned_world_model_meta={},
        tenant_id=tenant_id,
        product_id=product_id,
        domain=domain,
        product_version=product_version,
    )

    assert tenant_id is None
    assert "tenant_id" not in payload
    assert payload["product_id"] == "crm-pro"
