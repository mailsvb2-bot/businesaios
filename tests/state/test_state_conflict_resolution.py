from __future__ import annotations

from runtime.state.state_conflict_resolver import StateConflictResolver
from runtime.state.state_contract import StateObservation
from runtime.state.state_freshness_policy import FieldFreshnessPolicy, StateFreshnessPolicy


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


def test_state_conflict_resolution_prefers_known_over_unknown() -> None:
    resolver = StateConflictResolver()

    resolved = resolver.resolve(
        now_ms=5_000,
        field_path="ops.operator_on_call",
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
    resolver = StateConflictResolver(
        freshness_policy=StateFreshnessPolicy(default_max_future_skew_ms=100)
    )

    resolved = resolver.resolve(
        now_ms=1_000,
        field_path="finance.balance",
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
