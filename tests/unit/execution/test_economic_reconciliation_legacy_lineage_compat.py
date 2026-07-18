from __future__ import annotations

from execution.economic_multi_backend_reconciliation import (
    EconomicMultiBackendReconciliationBuilder,
)


def test_legacy_node_without_declared_lineage_is_not_falsely_corrupted():
    result = EconomicMultiBackendReconciliationBuilder().build(
        feedback_rows=[{"event_id": "evt-1"}],
        roi_rows=[],
        snapshot_rows=[],
        trace_rows=[],
        metrics_rows=[],
        bundle_payloads=[{"payload": {"feedback_rows": [{"event_id": "evt-1"}]}}],
        node_payloads=[
            {
                "node_id": "legacy-primary",
                "backend_role": "primary",
                "feedback_rows": [{"event_id": "evt-1"}],
                "metadata": {"import_validation_status": "valid"},
            }
        ],
    )

    assert result.corrupted_node_ids == ()
    assert result.metadata["lineage_invalid_node_ids"] == []
    assert result.authoritative_backend == "legacy-primary"


def test_declared_invalid_lineage_remains_fail_closed():
    result = EconomicMultiBackendReconciliationBuilder().build(
        feedback_rows=[{"event_id": "evt-1"}],
        roi_rows=[],
        snapshot_rows=[],
        trace_rows=[],
        metrics_rows=[],
        bundle_payloads=[{"payload": {"feedback_rows": [{"event_id": "evt-1"}]}}],
        node_payloads=[
            {
                "node_id": "forged-primary",
                "backend_role": "primary",
                "feedback_rows": [{"event_id": "evt-1"}],
                "export_manifest": {
                    "scope_lineage": {"parents": []},
                    "lineage_lock": {
                        "lineage_hash": "forged",
                        "parents": [],
                    },
                },
            }
        ],
    )

    assert result.corrupted_node_ids == ("forged-primary",)
    assert result.metadata["lineage_invalid_node_ids"] == ["forged-primary"]
    assert result.authoritative_backend is None
