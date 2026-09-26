from interfaces.api.business_autonomy_route_handlers import build_business_autonomy_route_handlers


def test_business_autonomy_route_handlers_return_dashboard_readiness_and_audit() -> None:
    handlers = build_business_autonomy_route_handlers()
    dashboard = handlers.get_dashboard()
    readiness = handlers.get_readiness()
    audit = handlers.get_audit(limit=10)

    assert "health_cards" in dashboard
    assert "overall_ready" in readiness
    assert "records" in audit


def test_business_autonomy_route_handlers_chaos_dry_run() -> None:
    handlers = build_business_autonomy_route_handlers()
    result = handlers.run_chaos_dry_run("barrier_restart_recovery")
    assert result["accepted"] is True
    assert result["executed"] is False


def test_business_autonomy_route_handlers_observability_exports() -> None:
    handlers = build_business_autonomy_route_handlers()
    report = handlers.get_observability_report()
    observability = handlers.export_observability_bundle("business-autonomy-test")
    audit = handlers.export_audit_bundle("business-autonomy-audit-test")

    assert "audit_event_count" in report
    assert observability["path"].endswith(".json")
    assert audit["path"].endswith(".json")


def test_business_autonomy_agent_identity_control_plane_lifecycle() -> None:
    from application.business_autonomy.registry import AgentIdentityRegistry
    from reliability.idempotency_store import InMemoryIdempotencyStore

    class MemoryEventStore:
        def __init__(self) -> None:
            self.events = []

        def append_event(self, event):
            self.events.append(dict(event))

        def iter_events(self, *, tenant_id, start_ms, end_ms=None, user_id=None, event_type=None):
            del user_id
            for event in self.events:
                if str(event.get("tenant_id") or "") != str(tenant_id):
                    continue
                if int(event.get("timestamp_ms") or 0) < int(start_ms):
                    continue
                if end_ms is not None and int(event.get("timestamp_ms") or 0) > int(end_ms):
                    continue
                if event_type is not None and str(event.get("event_type") or "") != str(event_type):
                    continue
                yield dict(event)

    registry = AgentIdentityRegistry(
        event_store=MemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )
    handlers = build_business_autonomy_route_handlers(
        stack={"agent_identity_registry": registry}
    )

    root = handlers.register_agent_identity(
        tenant_id="tenant-1",
        business_id="business-1",
        agent_id="root",
        idempotency_key="root-create",
        agent_type="business",
        agent_version="v1",
        capability_scope=("notify_owner", "launch_campaign"),
        budget_scope={"messages_per_day": 100.0},
        requested_by="owner-1",
    )
    assert root["agent_id"] == "root"
    assert root["lifecycle_status"] == "active"

    child = handlers.register_agent_identity(
        tenant_id="tenant-1",
        business_id="business-1",
        agent_id="child",
        idempotency_key="child-create",
        agent_type="worker",
        agent_version="v1",
        delegated_by="root",
        capability_scope=("notify_owner",),
        budget_scope={"messages_per_day": 50.0},
        requested_by="owner-1",
    )
    assert child["delegated_by"] == "root"

    listed = handlers.list_agent_identities(
        tenant_id="tenant-1",
        business_id="business-1",
    )
    assert listed["count"] == 2
    assert {item["agent_id"] for item in listed["identities"]} == {"root", "child"}

    revoked = handlers.revoke_agent_identity(
        tenant_id="tenant-1",
        business_id="business-1",
        agent_id="child",
        idempotency_key="child-revoke",
        requested_by="owner-1",
    )
    assert revoked["lifecycle_status"] == "revoked"
