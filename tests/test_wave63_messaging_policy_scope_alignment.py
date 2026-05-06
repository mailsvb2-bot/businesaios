from __future__ import annotations

from runtime.messaging_policy_alert_dedup.dedup_key import build_alert_notification_dedup_key
from runtime.messaging_policy_alert_subscriptions.subscription_parser import parse_subscription
from runtime.messaging_policy_alerts.service import MessagingPolicyAlertService
from runtime.messaging_policy_dashboard.service import MessagingPolicyDashboardService
from runtime.messaging_policy_readmodel.snapshot_key import build_snapshot_key
from runtime.messaging_policy_trace.group_key import build_trace_group_key
from runtime.messaging_policy_readmodel.read_service import MessagingPolicyReadService


class _TraceSearch:
    def __init__(self):
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return []


class _Dashboard:
    def __init__(self):
        self.calls = []

    def build(self, **kwargs):
        self.calls.append(kwargs)
        return {"alerts": []}


class _Detector:
    def detect(self, dashboard):
        return dashboard


class _Repo:
    def __init__(self):
        self.calls = []

    def get(self, **kwargs):
        self.calls.append(kwargs)
        return None


class _Rebuild:
    def __init__(self):
        self.calls = []

    def rebuild_one(self, **kwargs):
        self.calls.append(kwargs)
        return kwargs


def test_dashboard_service_normalizes_placeholder_tenant():
    trace = _TraceSearch()
    service = MessagingPolicyDashboardService(trace_search_service=trace)
    service.build(tenant_id="default", user_id="u1")
    assert trace.calls[-1]["tenant_id"] == "unknown_tenant"


def test_alert_service_normalizes_placeholder_tenant_before_dashboard():
    dashboard = _Dashboard()
    service = MessagingPolicyAlertService(dashboard_service=dashboard, detector=_Detector())
    service.build(tenant_id="legacy", user_id="u1")
    assert dashboard.calls[-1]["tenant_id"] == "unknown_tenant"


def test_subscription_parser_normalizes_placeholder_tenant():
    rec = parse_subscription({"recipient_user_id": "u1"}, tenant_id="default")
    assert rec is not None
    assert rec.tenant_id == "unknown_tenant"


def test_messaging_policy_keys_use_normalized_scope():
    assert build_snapshot_key(tenant_id="default", user_id="u", correlation_id="c")[0] == "unknown_tenant"
    assert build_trace_group_key(tenant_id="legacy", user_id="u", correlation_id="c")[0] == "unknown_tenant"
    assert build_alert_notification_dedup_key(tenant_id="default", recipient_user_id="u", channel="telegram", alert_code="a", affected_user_id="x").startswith("unknown_tenant|")


def test_read_service_rebuild_uses_normalized_scope():
    repo = _Repo()
    rebuild = _Rebuild()
    service = MessagingPolicyReadService(repository=repo, rebuild_service=rebuild)
    out = service.get_snapshot(tenant_id="default", user_id="u", correlation_id="c")
    assert repo.calls[-1]["tenant_id"] == "unknown_tenant"
    assert rebuild.calls[-1]["tenant_id"] == "unknown_tenant"
    assert out["tenant_id"] == "unknown_tenant"
