from __future__ import annotations

from dataclasses import dataclass

from runtime.state.state_contract import StateConflictRecord, StateFieldRecord, StateObservation
from runtime.state.state_freshness_policy import (
    NON_DECISION_FRESHNESS_STATUSES,
    TEMPORALLY_INVALID_FRESHNESS_STATUSES,
    StateFreshnessPolicy,
)
from runtime.state.state_provenance import (
    canonical_json_bytes,
    merge_evidence_refs,
    provenance_hash,
    provenance_payload,
)
from runtime.state.state_unknown_semantics import classify_value_kind, normalize_unknown

CANON_STATE_CONFLICT_RESOLVER = True


@dataclass(frozen=True)
class ResolvedField:
    record: StateFieldRecord
    conflict: StateConflictRecord | None = None


class StateConflictResolver:
    def __init__(self, *, freshness_policy: StateFreshnessPolicy | None = None) -> None:
        self._freshness_policy = freshness_policy or StateFreshnessPolicy()

    def resolve(
        self,
        *,
        now_ms: int,
        field_path: str,
        observations: tuple[StateObservation, ...],
        tenant_id: str | None = None,
        business_id: str | None = None,
    ) -> ResolvedField:
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
        stale_like = freshness.status in {"stale", "invalid_future"} | TEMPORALLY_INVALID_FRESHNESS_STATUSES
        decision_candidates = [
            item
            for item in ranked
            if self._freshness_policy.evaluate(now_ms=now_ms, observation=item).status
            not in NON_DECISION_FRESHNESS_STATUSES
        ]
        has_conflict = len(decision_candidates) > 1 and self._has_material_conflict(decision_candidates)
        authoritative_pairs = [
            (
                str(item.source),
                normalize_unknown(value=item.value, unknown=bool(item.unknown), absent=bool(item.absent)),
            )
            for item in decision_candidates
            if item.authoritative
        ]
        authoritative_sources = {source for source, _ in authoritative_pairs}
        authoritative_values = {
            canonical_json_bytes({"value": value[0], "unknown": value[1], "absent": value[2]})
            for _, value in authoritative_pairs
        }
        conflict_status = (
            "human_required"
            if has_conflict and len(authoritative_sources) > 1 and len(authoritative_values) > 1
            else "auto_resolved"
            if has_conflict
            else None
        )
        resolution_policy = (
            "authoritative_conflict_requires_human@v1"
            if conflict_status == "human_required"
            else "ranked_state_conflict_policy@v1"
        )

        winner_provenance_envelope = (
            dict(winner._trusted_provenance_envelope)
            if winner._trusted_provenance_hash
            else provenance_payload(
                observation=winner,
                tenant_id=tenant_id,
                business_id=business_id,
            )
        )
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
            provenance_hash=str(
                winner._trusted_provenance_hash
                or provenance_hash(observation=winner, tenant_id=tenant_id, business_id=business_id)
            ),
            evidence_refs=merge_evidence_refs(left=winner.evidence_refs, right=()),
            occurred_at_ms=winner.occurred_at_ms,
            valid_from_ms=winner.valid_from_ms,
            valid_until_ms=winner.valid_until_ms,
            superseded_at_ms=winner.superseded_at_ms,
            semantic_kind=winner.semantic_kind,
            candidates_considered=len(ranked),
            conflict=has_conflict,
            provenance_envelope=winner_provenance_envelope,
            meta={
                **{
                    key: value
                    for key, value in dict(winner.meta).items()
                    if key not in {"conflict_status", "resolution_policy"}
                },
                **(
                    {}
                    if not winner._trusted_business_fact_id
                    else {
                        "business_fact_supersedes_fact_id": (
                            str(winner._trusted_supersedes_fact_id)
                            if winner._trusted_supersedes_fact_id
                            else None
                        )
                    }
                ),
                "effective_ttl_ms": freshness.effective_ttl_ms,
                "age_ms": freshness.age_ms,
                **(
                    {}
                    if conflict_status is None
                    else {
                        "conflict_status": conflict_status,
                        "resolution_policy": resolution_policy,
                    }
                ),
            },
        )

        conflict = None
        if has_conflict:
            conflict_tenant_id = str(tenant_id or winner.tenant_id or "").strip()
            conflict_business_id = str(business_id or winner.business_id or "").strip()
            if not conflict_tenant_id or not conflict_business_id:
                raise ValueError("tenant_id and business_id are required for conflict identity")
            for item in decision_candidates:
                if item.tenant_id is not None and str(item.tenant_id) != conflict_tenant_id:
                    raise ValueError("conflict candidate tenant_id mismatch")
                if item.business_id is not None and str(item.business_id) != conflict_business_id:
                    raise ValueError("conflict candidate business_id mismatch")
            conflict = StateConflictRecord(
                field_path=str(field_path),
                tenant_id=conflict_tenant_id,
                business_id=conflict_business_id,
                chosen_source=str(record.source),
                chosen_provenance_hash=str(record.provenance_hash),
                candidate_sources=tuple(str(item.source) for item in decision_candidates),
                candidate_provenance_hashes=tuple(
                    str(
                        item._trusted_provenance_hash
                        or provenance_hash(observation=item, tenant_id=tenant_id, business_id=business_id)
                    )
                    for item in decision_candidates
                ),
                reason=self._explain_choice(now_ms=now_ms, winner=winner, observations=ranked),
                detected_at_ms=int(now_ms),
                status=str(conflict_status),
                resolution_policy=resolution_policy,
                resolution_evidence_refs=tuple(
                    ref.evidence_id or ref.uri or ref.checksum
                    for item in ranked
                    for ref in item.evidence_refs
                    if (ref.evidence_id or ref.uri or ref.checksum)
                ),
            )

        return ResolvedField(record=record, conflict=conflict)

    def _rank_key(self, *, now_ms: int, item: StateObservation) -> tuple[int, int, int, float, int, int, bytes]:
        freshness = self._freshness_policy.evaluate(now_ms=now_ms, observation=item)
        freshness_rank = {
            "fresh": 5,
            "stale_authoritative": 4,
            "stale": 3,
            "invalid_future": 0,
            "not_yet_valid": 0,
            "expired": 0,
            "superseded": 0,
        }.get(freshness.status, 1)

        value, unknown, absent = normalize_unknown(
            value=item.value, unknown=bool(item.unknown), absent=bool(item.absent)
        )
        known_rank = 0 if (unknown or absent) else 1

        return (
            freshness_rank,
            int(bool(item.authoritative)),
            known_rank,
            float(item.confidence),
            int(item.source_priority),
            int(item.observed_at_ms),
            canonical_json_bytes({"source": str(item.source), "value": value, "unknown": unknown, "absent": absent}),
        )

    def _has_material_conflict(self, items: list[StateObservation]) -> bool:
        normalized: set[bytes] = set()
        for item in items:
            value, unknown, absent = normalize_unknown(
                value=item.value, unknown=bool(item.unknown), absent=bool(item.absent)
            )
            normalized.add(canonical_json_bytes({"value": value, "unknown": unknown, "absent": absent}))
        return len(normalized) > 1

    def _explain_choice(self, *, now_ms: int, winner: StateObservation, observations: list[StateObservation]) -> str:
        freshness = self._freshness_policy.evaluate(now_ms=now_ms, observation=winner)
        return (
            f"winner={winner.source}; authoritative={bool(winner.authoritative)}; "
            f"priority={int(winner.source_priority)}; freshness={freshness.status}; "
            f"confidence={float(winner.confidence):0.3f}; observed_at_ms={int(winner.observed_at_ms)}; "
            f"candidates={len(observations)}"
        )
