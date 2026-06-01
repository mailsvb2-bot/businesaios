from __future__ import annotations

from datetime import UTC, datetime, timedelta

from application.business_autonomy.delayed_outcome_bridge import BusinessAutonomyDelayedOutcomeBridge
from application.business_autonomy.operator_admin_plane import UnifiedOperatorAdminPlane


def test_delayed_outcome_bridge_exposes_quarantine_summary(tmp_path) -> None:
    bridge = BusinessAutonomyDelayedOutcomeBridge(
        path=tmp_path / "delayed_outcomes.jsonl",
        state_path=tmp_path / "delayed_outcome_state.json",
        quarantine_path=tmp_path / "delayed_outcome_quarantine.jsonl",
    )
    bridge._write_state({
        "active": {
            "out_1": {
                "outcome_id": "out_1",
                "execution_id": "exec_1",
                "tenant_id": "tenant-a",
                "business_id": "biz-a",
                "goal_id": "goal-a",
                "expected_ready_at_utc": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
                "metadata": {},
                "status": "pending",
            }
        },
        "resolved": {},
        "quarantined": {},
    })
    sweep = bridge.sweep_expired()
    assert sweep.quarantined_count == 1
    summary = bridge.quarantine_summary()
    assert summary["quarantined_total"] == 1
    assert summary["by_reason"]["delayed_outcome_stale"] == 1
    rows = bridge.list_quarantined()
    assert rows[0].business_id == "biz-a"


def test_operator_admin_plane_surfaces_delayed_outcome_quarantine(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    bridge = BusinessAutonomyDelayedOutcomeBridge.default()
    bridge._write_state({
        "active": {},
        "resolved": {},
        "quarantined": {
            "out_1": {
                "outcome_id": "out_1",
                "execution_id": "exec_1",
                "tenant_id": "tenant-demo",
                "business_id": "biz-a",
                "goal_id": "goal-a",
                "expected_ready_at_utc": "2026-01-01T00:00:00+00:00",
                "metadata": {},
                "quarantine_reason": "delayed_outcome_stale",
                "quarantined_at_utc": "2026-01-02T00:00:00+00:00",
            }
        },
    })
    class _ReadModel:
        def fleet_metrics(self):
            return {"businesses_total": 0, "healthy_capabilities": 0, "pending_approvals": 0}

        def business_class_view(self, *, limit: int = 100):
            return ()

        def trust_capability_health(self, *, limit: int = 100):
            return ()

        def approval_bottleneck_view(self, *, limit: int = 100):
            return ()

        def cross_business_failures(self, *, limit: int = 100):
            return ()

        def export_links(self):
            return {}

        def delayed_outcome_health(self):
            return bridge.quarantine_summary() | {"active_total": 0}

        def delayed_outcome_quarantine_view(self, *, limit: int = 100):
            return ({"business_id": "biz-a", "reason": "delayed_outcome_stale"},)

    plane = UnifiedOperatorAdminPlane(read_model=_ReadModel())
    view = plane.get_fleet_view(limit=10)
    assert any(card.title == "Delayed Outcomes" for card in view.fleet_cards)
    assert len(view.delayed_outcome_quarantine_rows) == 1



def test_operator_admin_plane_surfaces_action_ledger_and_conflicts(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    bridge = BusinessAutonomyDelayedOutcomeBridge.default()
    bridge._write_state({
        "active": {},
        "resolved": {},
        "quarantined": {
            "out_1": {
                "outcome_id": "out_1",
                "execution_id": "exec_1",
                "tenant_id": "tenant-demo",
                "business_id": "biz-a",
                "goal_id": "goal-a",
                "expected_ready_at_utc": "2026-01-01T00:00:00+00:00",
                "metadata": {},
                "quarantine_reason": "delayed_outcome_stale",
                "quarantined_at_utc": "2026-01-02T00:00:00+00:00",
            }
        },
    })
    assert bridge.release_quarantined(outcome_id="out_1", released_by="operator", note="resume") is True

    append = tmp_path / 'runtime' / 'distributed' / 'append'
    append.mkdir(parents=True, exist_ok=True)
    (append / 'distributed_state_conflicts_state.json').write_text('{"items": {"tenant-demo:biz-a:business_registry": {"tenant_id": "tenant-demo", "business_id": "biz-a", "document": "business_registry", "status": "acknowledged", "acknowledged_by": "operator", "acknowledged_at_utc": "2026-01-02T00:00:00+00:00", "resolved_by": "", "resolution_note": "", "resolved_at_utc": ""}}}', encoding='utf-8')

    from application.business_autonomy.provider_catalog_fleet_read_model import ProviderCatalogFleetReadModel
    plane = UnifiedOperatorAdminPlane(read_model=ProviderCatalogFleetReadModel())
    view = plane.get_fleet_view(limit=10)
    assert any(card.title == "Distributed Conflicts" for card in view.fleet_cards)
    assert len(view.delayed_outcome_action_rows) >= 1
    assert view.delayed_outcome_action_rows[0]["action_type"] == "release"
    assert len(view.distributed_state_conflict_rows) == 1
    assert view.distributed_state_conflict_rows[0]["status"] == "acknowledged"
