from pathlib import Path

from execution.cross_run_economic_audit import CrossRunEconomicAuditBuilder
from execution.economic_store_wiring import EconomicStoreWiring


def test_economic_store_wiring_creates_jsonl_backends(tmp_path: Path) -> None:
    bundle = EconomicStoreWiring(root_dir=tmp_path).build()
    bundle.memory_store.upsert_payload({'event_id': 'evt-1', 'channel': 'ads'})
    bundle.roi_history_store.upsert_payload({'event_id': 'evt-1', 'channel': 'ads'})
    bundle.policy_snapshot_store.append_payload({'snapshot_id': 'snap-1', 'channel': 'ads'})
    assert bundle.memory_store.list_rows()[0].to_dict()['event_id'] == 'evt-1'
    assert bundle.roi_history_store.list_rows()[0].to_dict()['event_id'] == 'evt-1'
    assert bundle.policy_snapshot_store.list_rows()[0].to_dict()['snapshot_id'] == 'snap-1'


def test_cross_run_economic_audit_builder_deduplicates_events() -> None:
    audit = CrossRunEconomicAuditBuilder().build(
        feedback_rows=(
            {'event_id': 'evt-1', 'channel': 'ads', 'verified': True, 'realized_revenue': 10.0, 'approved_budget': 4.0, 'requested_budget': 5.0},
            {'event_id': 'evt-1', 'channel': 'ads', 'verified': True, 'realized_revenue': 10.0, 'approved_budget': 4.0, 'requested_budget': 5.0},
        ),
        roi_rows=(
            {'event_id': 'evt-1'},
            {'event_id': 'evt-1'},
        ),
        snapshot_rows=(
            {'snapshot_id': 'snap-1'},
            {'snapshot_id': 'snap-1'},
        ),
    ).to_dict()
    assert audit['duplicate_feedback_events'] == 1
    assert audit['duplicate_roi_events'] == 1
    assert audit['restart_resume_consistent'] is True
