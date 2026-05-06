from __future__ import annotations

from dataclasses import dataclass

from runtime.state.state_contract import StateConflictRecord, StateFieldRecord, StateObservation
from runtime.state.state_freshness_policy import StateFreshnessPolicy
from runtime.state.state_provenance import merge_evidence_refs, provenance_hash
from runtime.state.state_unknown_semantics import classify_value_kind, normalize_unknown


CANON_STATE_CONFLICT_RESOLVER = True


@dataclass(frozen=True)
class ResolvedField:
    record: StateFieldRecord
    conflict: StateConflictRecord | None = None


class StateConflictResolver:
    def __init__(self, *, freshness_policy: StateFreshnessPolicy | None = None) -> None:
        self._freshness_policy = freshness_policy or StateFreshnessPolicy()

    def resolve(self, *, now_ms: int, field_path: str, observations: tuple[StateObservation, ...]) -> ResolvedField:
        if not observations:
            raise ValueError("observations must not be empty")

        ranked = sorted(observations, key=lambda item: self._rank_key(now_ms=now_ms, item=item), reverse=True)
        winner = ranked[0]

        normalized_value, normalized_unknown, normalized_absent = normalize_unknown(
            value=winner.value,
            unknown=bool(winner.unknown),
            absent=bool(winner.absent),
        )
        freshness = self._freshness_policy.evaluate(now_ms=now_ms, observation=winner)
        stale_like = freshness.status in {"stale", "invalid_future"}
        has_conflict = len(ranked) > 1 and self._has_material_conflict(ranked)

        record = StateFieldRecord(
            field_path=str(field_path),
            value=normalized_value,
            value_kind=classify_value_kind(
                value=normalized_value,
                unknown=normalized_unknown,
                absent=normalized_absent,
                stale=stale_like,
                conflict=has_conflict,
            ),
            source=str(winner.source),
            observed_at_ms=int(winner.observed_at_ms),
            recorded_at_ms=int(winner.recorded_at_ms or winner.observed_at_ms),
            freshness_status=str(freshness.status),
            freshness_reason=str(freshness.reason),
            confidence=float(winner.confidence),
            source_priority=int(winner.source_priority),
            authoritative=bool(winner.authoritative),
            provenance_hash=provenance_hash(observation=winner),
            evidence_refs=merge_evidence_refs(left=winner.evidence_refs, right=()),
            candidates_considered=len(ranked),
            conflict=has_conflict,
            meta={
                "effective_ttl_ms": freshness.effective_ttl_ms,
                "age_ms": freshness.age_ms,
            },
        )

        conflict = None
        if has_conflict:
            conflict = StateConflictRecord(
                field_path=str(field_path),
                chosen_source=str(record.source),
                chosen_provenance_hash=str(record.provenance_hash),
                candidate_sources=tuple(str(item.source) for item in ranked),
                reason=self._explain_choice(now_ms=now_ms, winner=winner, observations=ranked),
            )

        return ResolvedField(record=record, conflict=conflict)

    def _rank_key(self, *, now_ms: int, item: StateObservation) -> tuple[int, int, int, float, int, int, str]:
        freshness = self._freshness_policy.evaluate(now_ms=now_ms, observation=item)
        freshness_rank = {
            "fresh": 5,
            "stale_authoritative": 4,
            "stale": 3,
            "invalid_future": 0,
        }.get(freshness.status, 1)

        value, unknown, absent = normalize_unknown(value=item.value, unknown=bool(item.unknown), absent=bool(item.absent))
        known_rank = 0 if (unknown or absent) else 1

        return (
            freshness_rank,
            int(bool(item.authoritative)),
            known_rank,
            float(item.confidence),
            int(item.source_priority),
            int(item.observed_at_ms),
            f"{str(item.source)}|{repr(value)}",
        )

    def _has_material_conflict(self, items: list[StateObservation]) -> bool:
        normalized: set[str] = set()
        for item in items:
            value, unknown, absent = normalize_unknown(value=item.value, unknown=bool(item.unknown), absent=bool(item.absent))
            normalized.add(repr((value, unknown, absent)))
        return len(normalized) > 1

    def _explain_choice(self, *, now_ms: int, winner: StateObservation, observations: list[StateObservation]) -> str:
        freshness = self._freshness_policy.evaluate(now_ms=now_ms, observation=winner)
        return (
            f"winner={winner.source}; authoritative={bool(winner.authoritative)}; "
            f"priority={int(winner.source_priority)}; freshness={freshness.status}; "
            f"confidence={float(winner.confidence):0.3f}; observed_at_ms={int(winner.observed_at_ms)}; "
            f"candidates={len(observations)}"
        )
