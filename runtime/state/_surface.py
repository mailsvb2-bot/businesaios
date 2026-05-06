from __future__ import annotations

from runtime.state.contract import (
    RUNTIME_STATE_PUBLIC_API,
    STATE_SYNTHESIS_CANON,
    STATE_SYNTHESIS_FORBIDS_DECISION_OWNERSHIP,
    STATE_SYNTHESIS_SUBORDINATE_TO_WORLD_STATE,
)
from runtime.state.state_audit_trail import FileStateAuditTrail
from runtime.state.state_compaction import StateCompactionPolicy, StateCompactor
from runtime.state.state_conflict_resolver import ResolvedField, StateConflictResolver
from runtime.state.state_contract import (
    ABSENT_VALUE_KIND,
    CONFLICT_VALUE_KIND,
    STALE_VALUE_KIND,
    STATE_SYNTHESIS_SCHEMA_VERSION,
    UNKNOWN_VALUE_KIND,
    StateAuditTrailPort,
    StateConflictRecord,
    StateDeltaLogPort,
    StateEvidenceRef,
    StateFieldRecord,
    StateObservation,
    StateSnapshotStorePort,
    StateSynthesisRequest,
    StateSynthesizedSnapshot,
)
from runtime.state.state_delta_log import FileStateDeltaLog
from runtime.state.state_freshness_policy import FieldFreshnessPolicy, FreshnessDecision, StateFreshnessPolicy
from runtime.state.state_provenance import merge_evidence_refs, normalize_evidence_refs, provenance_hash, provenance_payload
from runtime.state.state_snapshot_store import FileStateSnapshotStore, snapshot_from_dict
from runtime.state.state_synthesis_engine import (
    CANON_STATE_SYNTHESIS_ENGINE,
    STATE_SYNTHESIS_DOES_NOT_OWN_DECISIONS,
    StateSynthesisEngine,
    apply_synthesized_world_view,
    build_world_state_observations,
)
from runtime.state.state_unknown_semantics import classify_value_kind, is_unknown_marker, normalize_unknown

__all__ = [
    'CANON_RUNTIME_STATE_NAMESPACE',
    'CANON_STATE_SYNTHESIS_ENGINE',
    'RUNTIME_STATE_PUBLIC_API',
    'STATE_SYNTHESIS_CANON',
    'STATE_SYNTHESIS_DOES_NOT_OWN_DECISIONS',
    'STATE_SYNTHESIS_FORBIDS_DECISION_OWNERSHIP',
    'STATE_SYNTHESIS_SCHEMA_VERSION',
    'STATE_SYNTHESIS_SUBORDINATE_TO_WORLD_STATE',
    'ABSENT_VALUE_KIND',
    'CONFLICT_VALUE_KIND',
    'STALE_VALUE_KIND',
    'UNKNOWN_VALUE_KIND',
    'FieldFreshnessPolicy',
    'FileStateAuditTrail',
    'FileStateDeltaLog',
    'FileStateSnapshotStore',
    'FreshnessDecision',
    'ResolvedField',
    'StateAuditTrailPort',
    'StateCompactionPolicy',
    'StateCompactor',
    'StateConflictRecord',
    'StateConflictResolver',
    'StateDeltaLogPort',
    'StateEvidenceRef',
    'StateFieldRecord',
    'StateFreshnessPolicy',
    'StateObservation',
    'StateSnapshotStorePort',
    'StateSynthesisEngine',
    'StateSynthesisRequest',
    'StateSynthesizedSnapshot',
    'apply_synthesized_world_view',
    'build_world_state_observations',
    'classify_value_kind',
    'is_unknown_marker',
    'merge_evidence_refs',
    'normalize_evidence_refs',
    'normalize_unknown',
    'provenance_hash',
    'provenance_payload',
    'snapshot_from_dict',
]

CANON_RUNTIME_STATE_NAMESPACE = True


