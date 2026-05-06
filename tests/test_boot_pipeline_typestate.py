from __future__ import annotations

from runtime.platform.identity.entitlements import InMemoryEntitlementsProvider, InMemoryIdentityProvider
from runtime.boot.system_builder import SystemBuilder


def test_pipeline_allowed_wires_services() -> None:
    sb = SystemBuilder(
        default_product_id="organization_platform",
        identity_provider=InMemoryIdentityProvider(authenticated_users={("t1", "u1")}),
        entitlements_provider=InMemoryEntitlementsProvider(grants={}),
    )
    system = sb.build(tenant_id="t1", user_id="u1", entrypoint="telegram", hints={})
    assert system.access.allowed is True
    assert system.services


def test_pipeline_denied_has_access_denied_marker() -> None:
    sb = SystemBuilder(
        default_product_id="organization_platform",
        identity_provider=InMemoryIdentityProvider(authenticated_users=set()),
        entitlements_provider=InMemoryEntitlementsProvider(grants={}),
    )
    system = sb.build(tenant_id="t1", user_id="u1", entrypoint="telegram", hints={})
    assert system.access.allowed is False
    assert "access_denied" in system.services
