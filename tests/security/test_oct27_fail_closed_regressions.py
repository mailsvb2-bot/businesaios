"""Regression: public provider ingress and audit scopes fail closed."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from entrypoints.api.audit_route_handlers import AuditRouteHandlers
from observability.action_audit_log import ActionAuditLog
from observability.decision_audit_log import DecisionAuditLog
from security.emergency_security_revoke import EmergencySecurityRevoke


def test_audit_tenant_filter_applies_before_limit():
    actions = ActionAuditLog()
    decisions = DecisionAuditLog()
    for i in range(30):
        actions.record({"tenant_id": "other", "trace_id": "shared", "value": i})
        decisions.record_payload({"tenant_id": "other", "trace_id": "shared", "value": i})
    actions.record({"tenant_id": "mine", "trace_id": "shared", "value": 99})
    decisions.record_payload({"tenant_id": "mine", "trace_id": "shared", "value": 99})
    for i in range(30):
        actions.record({"tenant_id": "other", "trace_id": "shared", "value": 100+i})
        decisions.record_payload({"tenant_id": "other", "trace_id": "shared", "value": 100+i})
    handlers = AuditRouteHandlers(action_audit_log=actions, decision_audit_log=decisions)
    for reader in (handlers.list_actions, handlers.list_decisions):
        assert [x["value"] for x in reader(tenant_id="mine", limit=1)["records"]] == [99]
        assert [x["value"] for x in reader(tenant_id="mine", trace_id="shared", limit=1)["records"]] == [99]
        with pytest.raises(ValueError):
            reader(tenant_id="", limit=10)
    trace = handlers.latest_trace(tenant_id="mine", trace_id="shared")
    assert len(trace["actions"]) == len(trace["decisions"]) == 1


def test_emergency_revoke_never_reports_success_on_partial_failure():
    class Keys:
        def revoke(self, key_id):
            if key_id == "failed":
                raise RuntimeError("cannot revoke")
    class Tokens:
        def revoke(self, *, token_fingerprint, reason):
            if token_fingerprint == "failed":
                raise RuntimeError("cannot revoke token")
    incident = SimpleNamespace(open_incident=lambda **kw: 17)
    service = EmergencySecurityRevoke(key_provider=Keys(), token_revocation_store=Tokens(), incident_registry=incident)
    result = service.execute(reason="compromised", key_ids=["ok", "failed"], token_fingerprints=["ok", "failed"])
    assert result.success is False
    assert result.revoked_key_ids == ("ok",)
    assert result.revoked_token_fingerprints == ("ok",)
