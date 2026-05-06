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
