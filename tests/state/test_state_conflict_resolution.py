from __future__ import annotations

from runtime.state.state_conflict_resolver import StateConflictResolver
from runtime.state.state_contract import StateObservation, StateSynthesisRequest
from runtime.state.state_freshness_policy import FieldFreshnessPolicy, StateFreshnessPolicy
from runtime.state.state_synthesis_engine import StateSynthesisEngine


def test_state_conflict_resolution_prefers_authoritative_source_even_if_older_within_policy() -> None:
    resolver = StateConflictResolver(
        freshness_policy=StateFreshnessPolicy(
            default_ttl_ms=10_000,
            prefix_policies={"economy": FieldFreshnessPolicy(ttl_ms=10_000, allow_stale_if_authoritative=True)},
        )
    )

    resolved = resolver.resolve(
        now_ms=10_000,
        field_path="economy.cash_balance",
        tenant_id="tenant-1",
        business_id="business-1",
        observations=(
            StateObservation(
                field_path="economy.cash_balance",
                value=1100,
                source="ledger",
                observed_at_ms=4_000,
                authoritative=True,
                source_priority=200,
                confidence=0.90,
            ),
            StateObservation(
                field_path="economy.cash_balance",
                value=950,
                source="crm",
                observed_at_ms=9_500,
                authoritative=False,
                source_priority=20,
                confidence=0.99,
            ),
        ),
    )

    assert resolved.record.value == 1100
    assert resolved.record.source == "ledger"
    assert resolved.record.conflict is True
    assert resolved.conflict is not None
    assert resolved.conflict.status == "auto_resolved"


def test_state_conflict_resolution_prefers_known_over_unknown() -> None:
    resolver = StateConflictResolver()

    resolved = resolver.resolve(
        now_ms=5_000,
        field_path="ops.operator_on_call",
        tenant_id="tenant-1",
        business_id="business-1",
        observations=(
            StateObservation(
                field_path="ops.operator_on_call",
                value="unknown",
                source="cache",
                observed_at_ms=4_900,
                unknown=True,
                source_priority=100,
            ),
            StateObservation(
                field_path="ops.operator_on_call",
                value="sergey",
                source="schedule",
                observed_at_ms=4_000,
                source_priority=80,
            ),
        ),
    )

    assert resolved.record.value == "sergey"
    assert resolved.record.value_kind == "conflict"


def test_state_conflict_resolution_rejects_invalid_future_even_if_authoritative() -> None:
    resolver = StateConflictResolver(freshness_policy=StateFreshnessPolicy(default_max_future_skew_ms=100))

    resolved = resolver.resolve(
        now_ms=1_000,
        field_path="finance.balance",
        tenant_id="tenant-1",
        business_id="business-1",
        observations=(
            StateObservation(
                field_path="finance.balance",
                value=100,
                source="ledger",
                observed_at_ms=2_000,
                authoritative=True,
                source_priority=100,
            ),
            StateObservation(
                field_path="finance.balance",
                value=95,
                source="cache",
                observed_at_ms=900,
                authoritative=False,
                source_priority=10,
            ),
        ),
    )

    assert resolved.record.value == 95
    assert resolved.record.source == "cache"


def test_state_conflict_between_distinct_authoritative_sources_requires_human_resolution() -> None:
    snapshot = StateSynthesisEngine().synthesize(
        StateSynthesisRequest(
            tenant_id="tenant-1",
            business_id="business-1",
            now_ms=5_000,
            observations=(
                StateObservation(
                    field_path="finance.cash_balance",
                    value=100,
                    source="bank:a",
                    observed_at_ms=4_900,
                    authoritative=True,
                    source_priority=100,
                ),
                StateObservation(
                    field_path="finance.cash_balance",
                    value=120,
                    source="bank:b",
                    observed_at_ms=4_800,
                    authoritative=True,
                    source_priority=100,
                ),
            ),
        )
    )

    [conflict] = snapshot.conflicts
    assert conflict.status == "human_required"
    assert conflict.resolution_policy == "authoritative_conflict_requires_human@v1"
    assert snapshot.fields["finance.cash_balance"].meta["conflict_status"] == "human_required"
