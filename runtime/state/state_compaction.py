from __future__ import annotations

from dataclasses import dataclass

from runtime.state.state_contract import StateFieldRecord, StateSynthesizedSnapshot


CANON_STATE_COMPACTION = True


@dataclass(frozen=True)
class StateCompactionPolicy:
    keep_conflicts: bool = True
    prune_audit_candidates: bool = True


@dataclass(frozen=True)
class StateCompactor:
    policy: StateCompactionPolicy = StateCompactionPolicy()

    def compact(self, snapshot: StateSynthesizedSnapshot) -> StateSynthesizedSnapshot:
        compacted_fields = {}
        for field_path, record in snapshot.fields.items():
            meta = dict(record.meta)
            if self.policy.prune_audit_candidates:
                meta.pop("candidate_payloads", None)

            compacted_fields[field_path] = StateFieldRecord(
                field_path=record.field_path,
                value=record.value,
                value_kind=record.value_kind,
                source=record.source,
                observed_at_ms=record.observed_at_ms,
                recorded_at_ms=record.recorded_at_ms,
                freshness_status=record.freshness_status,
                freshness_reason=record.freshness_reason,
                confidence=record.confidence,
                source_priority=record.source_priority,
                authoritative=record.authoritative,
                provenance_hash=record.provenance_hash,
                evidence_refs=record.evidence_refs,
                candidates_considered=record.candidates_considered,
                conflict=record.conflict,
                meta=meta,
            )

        conflicts = snapshot.conflicts if self.policy.keep_conflicts else ()
        audit = dict(snapshot.audit)
        audit["compacted"] = True

        return StateSynthesizedSnapshot(
            state_id=snapshot.state_id,
            tenant_id=snapshot.tenant_id,
            business_id=snapshot.business_id,
            synthesized_at_ms=snapshot.synthesized_at_ms,
            schema_version=snapshot.schema_version,
            values=dict(snapshot.values),
            fields=compacted_fields,
            conflicts=tuple(conflicts),
            source_watermarks=dict(snapshot.source_watermarks),
            audit=audit,
            meta=dict(snapshot.meta),
        )
