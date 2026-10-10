"""Prove support-case access is narrow and cannot grant general audit rights."""
from __future__ import annotations

from compliance.data_classification import DataCategory, DataSensitivity
from governance.permission_matrix import permissions_for_roles
from governance.rbac_contract import ActorContext, Permission, RoleId
from security.access_policy import DataAccessPolicy, SecurityAction, SecurityResource


def _route_verdict(resource_id: str, *, role: RoleId = RoleId.SUPPORT, scopes=("support_case_manage",), kind="api_authentication"):
    policy = DataAccessPolicy()
    classified = policy.classify_payload(
        asset_id="api-test", name="api_authentication api_authentication",
        content_type="application/json", tags=("internal", "token", "control_plane"),
    )
    assert classified.category in (DataCategory.RESTRICTED, DataCategory.REGULATED)
    assert classified.sensitivity in (DataSensitivity.CRITICAL, DataSensitivity.HIGH)
    actor = ActorContext(
        actor_id="operator-one", tenant_id="tenant-a", role_ids=frozenset({role}),
        attributes={"scopes": list(scopes)},
    )
    resource = SecurityResource(
        resource_type=kind, resource_id=resource_id, tenant_id="tenant-a",
        classification=classified, encryption_required=True,
    )
    return policy.evaluate(
        actor=actor, action=SecurityAction.READ, resource=resource,
        transport_encrypted=True,
    )


def test_support_key_can_authenticate_only_bounded_support_routes():
    routes = (
        "GET:/platform-support/session", "GET:/platform-support/cases",
        "GET:/platform-support/cases/0c2d6f9e-558a-42ba-aa3e-99135c3be0aa/history",
        "POST:/platform-support/cases/0c2d6f9e-558a-42ba-aa3e-99135c3be0aa/claim",
        "POST:/platform-support/cases/0c2d6f9e-558a-42ba-aa3e-99135c3be0aa/release",
        "POST:/platform-support/cases/0c2d6f9e-558a-42ba-aa3e-99135c3be0aa/resolve",
    )
    for route in routes:
        result = _route_verdict(route)
        assert result.allowed, (route, result.reason)
        assert result.required_permission is Permission.VIEW_SUPPORT_CASE


def test_support_key_cannot_read_audit_other_business_or_unregistered_endpoint():
    roles = permissions_for_roles(frozenset({RoleId.SUPPORT}))
    assert Permission.VIEW_SUPPORT_CASE in roles
    assert Permission.VIEW_AUDIT not in roles
    assert Permission.EXECUTE_INTERNAL_WRITE not in roles
    forbidden = (
        "GET:/control-plane/audit",
        "GET:/business-workspace/support-cases",
        "GET:/platform-support/cases/stolen",
        "GET:/platform-support/cases/not-a-uuid/history",
        "GET:/platform-support/cases/0c2d6f9e-558a-42ba-aa3e-99135c3be0aa/raw-audit",
        "GET:/platform-support/cases/0c2d6f9e-558a-42ba-aa3e-99135c3be0aa/history/../../audit",
        "POST:/platform-support/cases/0c2d6f9e-558a-42ba-aa3e-99135c3be0aa/history",
        "DELETE:/platform-support/cases",
        "POST:/platform-support/cases",
        "POST:/platform-support/cases/0c2d6f9e-558a-42ba-aa3e-99135c3be0aa/reopen",
        "GET:/platform-support/cases/0c2d6f9e-558a-42ba-aa3e-99135c3be0aa/claim",
        "GET:/platform-support/cases/../audit",
    )
    for route in forbidden:
        result = _route_verdict(route)
        assert not result.allowed, (route, result.reason)
        assert result.reason == "missing_permission"


def test_support_special_permission_cannot_be_triggered_by_missing_scope_or_wrong_role_or_resource():
    good_route = "GET:/platform-support/session"
    assert not _route_verdict(good_route, scopes=()).allowed
    assert not _route_verdict(good_route, role=RoleId.VIEWER).allowed
    assert not _route_verdict(good_route, kind="business_fact").allowed
    history_route = "GET:/platform-support/cases/0c2d6f9e-558a-42ba-aa3e-99135c3be0aa/history"
    assert not _route_verdict(history_route, scopes=()).allowed
    assert not _route_verdict(history_route, role=RoleId.VIEWER).allowed
    assert not _route_verdict(history_route, kind="business_fact").allowed
