from execution.economic_replay_epoch_guard import EconomicReplayEpochGuard
from execution.economic_scope_lineage import EconomicScopeLineageGuard


def test_scope_lineage_allows_declared_migration() -> None:
    verdict = EconomicScopeLineageGuard().validate(
        current_scope={'tenant_id': 'tenant-a'},
        incoming_scope={'tenant_id': 'tenant-b'},
        declared_lineage={
            'old_scope': {'tenant_id': 'tenant-a'},
            'new_scope': {'tenant_id': 'tenant-b'},
        },
    )
    assert verdict.migration_allowed is True


def test_replay_epoch_guard_rejects_overlap() -> None:
    verdict = EconomicReplayEpochGuard().validate(
        current_state={'meta': {'economic_replay_epoch': 'epoch-1'}},
        incoming_payload={'metadata': {'replay_epoch': 'epoch-2'}},
    )
    assert verdict.accepted is False
