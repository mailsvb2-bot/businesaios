from __future__ import annotations

from dataclasses import replace

from runtime.state.state_contract import (
    StateConflictRecord,
    StateConflictResolution,
    StateFieldRecord,
    StateObservation,
    StateSynthesisRequest,
    StateSynthesizedSnapshot,
)
from runtime.state.state_freshness_policy import NON_DECISION_FRESHNESS_STATUSES, StateFreshnessPolicy
from runtime.state.state_provenance import provenance_hash, validate_record_provenance

CANON_STATE_CONFLICT_RESOLUTION_HELPER = True
STATE_CONFLICT_RESOLUTION_DOES_NOT_OWN_STATE = True


def validate_conflict_resolutions(
    *,
    request: StateSynthesisRequest,
    base_snapshot: StateSynthesizedSnapshot | None,
) -> dict[str, StateConflictResolution]:
    if not request.conflict_resolutions:
        return {}
    if base_snapshot is None:
        raise ValueError("conflict resolution requires a base_snapshot with an unresolved conflict")
    unresolved = {
        item.field_path: item for item in base_snapshot.conflicts if item.status in {"open", "human_required"}
    }
    validated: dict[str, StateConflictResolution] = {}
    for resolution in request.conflict_resolutions:
        conflict = unresolved.get(resolution.field_path)
        if conflict is None:
            raise ValueError(f"no unresolved conflict for field_path: {resolution.field_path}")
        if conflict.tenant_id != request.tenant_id or conflict.business_id != request.business_id:
            raise ValueError(f"conflict scope mismatch for field_path: {resolution.field_path}")
        if str(resolution.conflict_id) != str(conflict.conflict_id):
            raise ValueError(f"conflict_id mismatch for field_path: {resolution.field_path}")
        if int(resolution.resolved_at_ms) < int(conflict.detected_at_ms):
            raise ValueError(f"resolution predates conflict detection: {resolution.field_path}")
        allowed_hashes = set(conflict.candidate_provenance_hashes)
        if not allowed_hashes:
            allowed_hashes.add(str(conflict.chosen_provenance_hash))
        if str(resolution.selected_provenance_hash) not in allowed_hashes:
            raise ValueError(f"selected_provenance_hash is not a candidate for conflict: {resolution.field_path}")
        validated[resolution.field_path] = resolution
    return validated


def unresolved_base_conflict(
    *,
    base_snapshot: StateSynthesizedSnapshot | None,
    field_path: str,
) -> StateConflictRecord | None:
    if base_snapshot is None:
        return None
    return next(
        (
            item
            for item in base_snapshot.conflicts
            if item.field_path == field_path and item.status in {"open", "human_required"}
        ),
        None,
    )


def base_observation_from_record(
    *,
    base_snapshot: StateSynthesizedSnapshot,
    field_path: str,
    record: StateFieldRecord,
) -> StateObservation:
    trusted_hash, trusted_envelope = validate_record_provenance(
        record=record,
        tenant_id=base_snapshot.tenant_id,
        business_id=base_snapshot.business_id,
    )
    observation = StateObservation(
        field_path=field_path,
        value=record.value,
        source=record.source,
        observed_at_ms=int(record.observed_at_ms),
        recorded_at_ms=int(record.recorded_at_ms),
        occurred_at_ms=record.occurred_at_ms,
        valid_from_ms=record.valid_from_ms,
        valid_until_ms=record.valid_until_ms,
        superseded_at_ms=record.superseded_at_ms,
        confidence=float(record.confidence),
        source_priority=int(record.source_priority),
        authoritative=bool(record.authoritative),
        ttl_ms=record.meta.get("effective_ttl_ms"),
        unknown=record.value_kind == "unknown",
        absent=record.value_kind == "absent",
        evidence_refs=tuple(record.evidence_refs),
        semantic_kind=record.semantic_kind,
        meta={**dict(record.meta), "hydrated_from_state_id": base_snapshot.state_id},
        tenant_id=base_snapshot.tenant_id,
        business_id=base_snapshot.business_id,
    )
    object.__setattr__(observation, "_trusted_provenance_hash", trusted_hash)
    object.__setattr__(observation, "_trusted_provenance_envelope", trusted_envelope)
    return observation


def observation_provenance_hash(
    observation: StateObservation,
    *,
    tenant_id: str,
    business_id: str,
) -> str:
    # Request observations are untrusted and must always be hashed from their full scoped payload.
    return provenance_hash(observation=observation, tenant_id=tenant_id, business_id=business_id)


def carry_unresolved_conflict(
    *,
    resolve_field,
    freshness_policy: StateFreshnessPolicy,
    now_ms: int,
    base_snapshot: StateSynthesizedSnapshot | None,
    conflict: StateConflictRecord,
    incoming_observations: tuple[StateObservation, ...],
) -> tuple[StateFieldRecord, StateConflictRecord]:
    if base_snapshot is None or conflict.field_path not in base_snapshot.fields:
        raise ValueError(f"unresolved conflict is missing its base field: {conflict.field_path}")
    base_record = base_snapshot.fields[conflict.field_path]
    base_observation = base_observation_from_record(
        base_snapshot=base_snapshot,
        field_path=conflict.field_path,
        record=base_record,
    )
    current = resolve_field(
        now_ms=now_ms,
        field_path=conflict.field_path,
        observations=(base_observation,),
        tenant_id=conflict.tenant_id,
        business_id=conflict.business_id,
    ).record

    candidate_sources = list(conflict.candidate_sources)
    candidate_hashes = list(conflict.candidate_provenance_hashes)
    if not candidate_hashes and conflict.chosen_provenance_hash:
        candidate_hashes.append(str(conflict.chosen_provenance_hash))
    changed = False
    for observation in incoming_observations:
        if observation._trusted_provenance_hash:
            # Hydrated base observations preserve durable identity and are not new evidence.
            continue
        freshness = freshness_policy.evaluate(now_ms=now_ms, observation=observation)
        if freshness.status in NON_DECISION_FRESHNESS_STATUSES:
            continue
        candidate_hash = observation_provenance_hash(
            observation, tenant_id=conflict.tenant_id, business_id=conflict.business_id
        )
        if candidate_hash in candidate_hashes:
            continue
        candidate_hashes.append(candidate_hash)
        candidate_sources.append(str(observation.source))
        changed = True

    carried_conflict = conflict
    if changed:
        carried_conflict = StateConflictRecord(
            field_path=conflict.field_path,
            tenant_id=conflict.tenant_id,
            business_id=conflict.business_id,
            chosen_source=conflict.chosen_source,
            chosen_provenance_hash=conflict.chosen_provenance_hash,
            candidate_sources=tuple(candidate_sources),
            candidate_provenance_hashes=tuple(candidate_hashes),
            reason=f"{conflict.reason}; unresolved conflict received new decision-eligible evidence",
            conflict_kind=conflict.conflict_kind,
            detected_at_ms=int(now_ms),
            status=conflict.status,
            resolution_policy=conflict.resolution_policy,
            resolution_evidence_refs=conflict.resolution_evidence_refs,
        )

    record = replace(
        current,
        value_kind=base_record.value_kind,
        source=base_record.source,
        provenance_hash=base_record.provenance_hash,
        evidence_refs=tuple(base_record.evidence_refs),
        conflict=True,
        candidates_considered=max(current.candidates_considered, len(carried_conflict.candidate_sources)),
        meta={
            **dict(base_record.meta),
            "effective_ttl_ms": current.meta.get("effective_ttl_ms"),
            "age_ms": current.meta.get("age_ms"),
            "conflict_status": carried_conflict.status,
            "resolution_policy": carried_conflict.resolution_policy,
            "conflict_id": carried_conflict.conflict_id,
        },
    )
    return record, carried_conflict


def apply_conflict_resolution(
    *,
    resolve_field,
    freshness_policy: StateFreshnessPolicy,
    request: StateSynthesisRequest,
    base_snapshot: StateSynthesizedSnapshot | None,
    conflict: StateConflictRecord,
    resolution: StateConflictResolution,
) -> tuple[StateFieldRecord, StateConflictRecord]:
    if base_snapshot is None or conflict.field_path not in base_snapshot.fields:
        raise ValueError(f"conflict resolution is missing its base field: {conflict.field_path}")
    base_record = base_snapshot.fields[conflict.field_path]
    allowed_hashes = set(conflict.candidate_provenance_hashes)
    if not allowed_hashes:
        allowed_hashes.add(str(conflict.chosen_provenance_hash))

    selected: StateObservation | None = None
    if str(resolution.selected_provenance_hash) == str(base_record.provenance_hash):
        selected = base_observation_from_record(
            base_snapshot=base_snapshot,
            field_path=conflict.field_path,
            record=base_record,
        )
        base_freshness = freshness_policy.evaluate(now_ms=request.now_ms, observation=selected)
        if base_freshness.status in NON_DECISION_FRESHNESS_STATUSES:
            raise ValueError(f"selected base conflict candidate is not decision-eligible: {conflict.field_path}")

    for observation in request.observations:
        if observation.field_path != conflict.field_path:
            continue
        freshness = freshness_policy.evaluate(now_ms=request.now_ms, observation=observation)
        candidate_hash = observation_provenance_hash(
            observation, tenant_id=request.tenant_id, business_id=request.business_id
        )
        if freshness.status not in NON_DECISION_FRESHNESS_STATUSES and candidate_hash not in allowed_hashes:
            raise ValueError(f"conflict changed by new candidate before resolution: {conflict.field_path}")
        if candidate_hash != resolution.selected_provenance_hash:
            continue
        if freshness.status in NON_DECISION_FRESHNESS_STATUSES:
            raise ValueError(f"selected conflict candidate is not decision-eligible: {conflict.field_path}")
        selected = observation

    if selected is None:
        raise ValueError(f"selected conflict candidate must be re-submitted for resolution: {conflict.field_path}")

    resolved = resolve_field(
        now_ms=request.now_ms,
        field_path=conflict.field_path,
        observations=(selected,),
        tenant_id=request.tenant_id,
        business_id=request.business_id,
    ).record
    evidence_ids = tuple(str(item.evidence_id or item.uri or item.checksum) for item in resolution.evidence_refs)
    resolved = replace(
        resolved,
        conflict=False,
        candidates_considered=max(resolved.candidates_considered, len(conflict.candidate_sources)),
        meta={
            **{
                key: value
                for key, value in dict(resolved.meta).items()
                if key not in {"conflict_status", "resolution_policy"}
            },
            "conflict_status": "resolved",
            "resolution_policy": "human_evidence_bound_resolution@v1",
            "resolved_conflict_id": conflict.conflict_id,
            "resolved_by": resolution.resolved_by,
            "resolved_at_ms": int(resolution.resolved_at_ms),
            "resolution_evidence_refs": evidence_ids,
            "resolution_reason": resolution.reason,
        },
    )
    resolved_conflict = replace(
        conflict,
        chosen_source=resolved.source,
        chosen_provenance_hash=resolved.provenance_hash,
        reason=(
            f"human_resolution resolved_by={resolution.resolved_by}; "
            f"selected_provenance_hash={resolution.selected_provenance_hash}"
        ),
        status="resolved",
        resolution_policy="human_evidence_bound_resolution@v1",
        resolution_evidence_refs=evidence_ids,
    )
    return resolved, resolved_conflict
