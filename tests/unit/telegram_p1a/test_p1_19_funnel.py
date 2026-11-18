"""P1-19: normalized funnel — won / lost / stale and per-stage conversion per source."""

from __future__ import annotations

from functools import partial
from types import SimpleNamespace

from application.business_flows import cockpit_sales as sales_center
from runtime.handler_impl.domains.business_flow_ops import handle_sales_pipeline

DAY = 86_400_000
NOW = 1_800_000_000_000


def _rows(*items):
    return [(ts, p) for ts, p in items]


def test_pipeline_funnel_counts_highest_stage_reached_won_lost_and_stale():
    rows = _rows(
        (NOW - 30 * DAY, {"step": "lead_added", "lead_id": "a"}),
        (NOW - 29 * DAY, {"step": "lead_event", "lead_id": "a", "event": "contact", "stage": "engaged"}),
        (NOW - 28 * DAY, {"step": "lead_event", "lead_id": "a", "event": "need", "stage": "need_known"}),
        (NOW - 27 * DAY, {"step": "lead_event", "lead_id": "a", "event": "declined", "stage": "lost"}),
        (NOW - 2 * DAY, {"step": "lead_inbound", "lead_id": "b"}),
        (NOW - DAY, {"step": "lead_event", "lead_id": "b", "event": "paid", "stage": "won"}),
        (NOW - 20 * DAY, {"step": "lead_added", "lead_id": "c"}),
        (NOW - 1, {"step": "lead_note", "lead_id": "ghost"}),  # unknown lead: ignored
    )
    f = sales_center.pipeline_funnel(rows, now_ms=NOW)
    assert (f["won"], f["lost"], f["open"], f["stale"]) == (1, 1, 1, 1)
    assert f["reached"]["engaged"] == 2 and f["reached"]["need_known"] == 2 and f["reached"]["won"] == 1
    first = f["stage_conversion"][0]
    assert first == {"from": "discovered", "to": "engaged", "reached": 2, "base": 3, "rate": round(2 / 3, 4)}
    assert f["win_rate"] == 0.5
    assert sales_center.pipeline_funnel([], now_ms=NOW) is None


def test_deal_funnel_maps_provider_stages_and_reports_unmapped():
    def d(stage, upd=NOW, status="active"):
        return SimpleNamespace(stage_key=stage, updated_at_ms=upd, lifecycle_status=status)
    deals = [d("appointmentscheduled", NOW - 30 * DAY), d("contractsent"), d("closedwon"), d("closedlost"),
             d("custom_stage_42"), d("closedwon", status="archived")]
    f = sales_center.deal_funnel(deals, provider_key="hubspot", now_ms=NOW)
    assert (f["won"], f["lost"], f["open"], f["stale"], f["unmapped"]) == (1, 1, 2, 1, 1)
    assert f["reached"]["checkout"] == 2 and f["reached"]["won"] == 1 and f["basis"] == "current_stage"
    assert sales_center.normalize_stage("hubspot", "ClosedWon") == "won"
    assert sales_center.normalize_stage("unknown_crm", "closedwon") is None
    assert sales_center.deal_funnel([], provider_key="hubspot", now_ms=NOW) is None


def test_sources_carry_the_funnel_from_the_real_pipeline(flow):
    import entrypoints.api.provider_admin_route_handlers as mod

    run = partial(flow.run, partial(handle_sales_pipeline, now_ms=NOW))
    run(op="add", arg="Анна | сайт")
    lead_id = flow.store.events[-1]["payload"]["lead_id"]
    run(op="event", arg="1 contact")
    run(op="event", arg="1 paid")

    class H(mod.ProviderAdminRouteHandlers):
        def list_provider_catalog(self, **_):
            return {"providers": []}

    out = H(customer_event_store=flow.store).get_sales_sources(tenant_id="t1", business_id="b1")
    funnel = out["sources"][0]["funnel"]
    assert funnel["won"] == 1 and funnel["reached"]["engaged"] == 1 and lead_id
