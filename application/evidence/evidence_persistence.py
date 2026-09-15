from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from application.effects.effect_outcome_vocabulary import (
    normalize_outcome_status,
    outcome_is_verified,
)
from application.evidence.evidence_feedback_state import (
    apply_feedback_to_world_state as _apply_feedback_world_state,
)
from execution.canonical_persistence_vocabulary import (
    canonical_memory_record,
    canonical_persistence_outcome_record,
)
from execution.evidence_persistence_feedback import (
    compact_evidence_payload as _compact_evidence_payload,
)
from execution.evidence_persistence_feedback import (
    compact_verification_payload as _compact_verification_payload,
)
from execution.evidence_persistence_feedback import (
    persistence_key as _persistence_key,
)
from execution.evidence_persistence_feedback import (
    refs_from_verification as _refs_from_verification,
)
from execution.evidence_persistence_reliability import EvidencePersistenceReliabilitySupport
from storage.evidence_store import EvidenceRecord, EvidenceStore

CANON_EVIDENCE_PERSISTENCE = True
CANON_MEMORY_EVIDENCE_PERSISTENCE = True
logger = logging.getLogger(__name__)


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _text(value: object) -> str:
    return str(value or '').strip()


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class PersistenceArtifacts:
    evidence_records: tuple[dict[str, Any], ...]
    outcome_record: dict[str, Any] | None
    memory_record: dict[str, Any] | None
    persistence_receipt: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'evidence_records': [dict(item) for item in self.evidence_records],
            'outcome_record': None if self.outcome_record is None else dict(self.outcome_record),
            'memory_record': None if self.memory_record is None else dict(self.memory_record),
            'persistence_receipt': None if self.persistence_receipt is None else dict(self.persistence_receipt),
        }


class EvidencePersistenceService:
    def __init__(
        self,
        *,
        business_memory_store: Any | None = None,
        business_memory_service: Any | None = None,
        checkpoint_store: Any | None = None,
        idempotency_store: Any | None = None,
        outbox_store: Any | None = None,
        replay_guard: Any | None = None,
        reconciliation_service: Any | None = None,
        tenant_default: str = 'system',
        reliability_namespace: str = 'evidence_persistence',
        reliability_operation: str = 'persist_feedback',
        idempotency_owner_id: str = 'evidence-persistence',
        evidence_store: EvidenceStore | None = None,
    ) -> None:
        self._business_memory_store = business_memory_store
        self._evidence_store = evidence_store
        self._business_memory_service = business_memory_service
        self._tenant_default = str(tenant_default or 'system')
        self._reliability = EvidencePersistenceReliabilitySupport(
            checkpoint_store=checkpoint_store,
            idempotency_store=idempotency_store,
            outbox_store=outbox_store,
            replay_guard=replay_guard,
            reconciliation_service=reconciliation_service,
            tenant_default=self._tenant_default,
            reliability_namespace=str(reliability_namespace or 'evidence_persistence'),
            reliability_operation=str(reliability_operation or 'persist_feedback'),
            idempotency_owner_id=str(idempotency_owner_id or 'evidence-persistence'),
        )

    def _attach_reliability_receipt(
        self,
        *,
        tenant_id: str,
        business_id: str,
        run_id: str,
        step_index: int,
        action_id: str,
        action_type: str = '',
        verification_result: Mapping[str, Any] | None = None,
        execution_result: Mapping[str, Any] | None = None,
        receipt: dict[str, Any],
    ) -> dict[str, Any]:
        return self._reliability.attach_reliability_receipt(
            tenant_id=tenant_id,
            business_id=business_id,
            run_id=run_id,
            step_index=step_index,
            action_id=action_id,
            action_type=action_type,
            verification_result=verification_result,
            execution_result=execution_result,
            receipt=receipt,
            logger=logger,
        )

    def build_feedback_artifacts(
        self,
        *,
        verification_result: Mapping[str, Any] | None,
        action: Mapping[str, Any] | None = None,
        execution_receipt: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        verification_payload = _safe_dict(verification_result)
        context = _safe_dict(verification_payload.get('context'))
        action_payload = _safe_dict(action) or _safe_dict(context.get('action'))
        execution_payload = _safe_dict(execution_receipt) or _safe_dict(context.get('execution_receipt'))
        step_index_value = action_payload.get('step_index')
        if step_index_value is None:
            step_index_value = execution_payload.get('step_index')
        step_index = int(step_index_value or 0)
        persisted_outcome = _compact_verification_payload(
            verification_payload,
            action=action_payload,
            execution_receipt=execution_payload,
        )
        persisted_evidence = _compact_evidence_payload(verification_payload)
        receipt = {
            'persistence_key': _persistence_key(
                tenant_id=_text(action_payload.get('tenant_id') or execution_payload.get('tenant_id')),
                business_id=_text(action_payload.get('business_id') or execution_payload.get('business_id')),
                run_id=_text(action_payload.get('run_id') or action_payload.get('decision_id') or execution_payload.get('decision_id')),
                step_index=step_index,
                outcome=persisted_outcome,
            ),
            'persisted_at': _utc_now().isoformat(),
        }
        payload = {
            'persisted_outcome': persisted_outcome,
            'persisted_evidence': persisted_evidence,
            'persistence_receipt': self._attach_reliability_receipt(
                tenant_id=_text(action_payload.get('tenant_id') or execution_payload.get('tenant_id')) or self._tenant_default,
                business_id=_text(action_payload.get('business_id') or execution_payload.get('business_id')),
                run_id=_text(action_payload.get('run_id') or action_payload.get('decision_id') or execution_payload.get('decision_id')) or 'feedback-artifacts',
                step_index=step_index,
                action_id=_text(persisted_outcome.get('action_id')),
                action_type=_text(persisted_outcome.get('action_type')),
                verification_result=verification_payload,
                execution_result=execution_payload,
                receipt=receipt,
            ),
        }
        verification = _safe_dict(verification_payload.get('verification'))
        engine = _safe_dict(verification.get('engine'))
        persistence = _safe_dict(engine.get('persistence'))
        if persistence:
            payload['verification_persistence'] = persistence
        return payload

    @staticmethod
    def _canonical_evidence_id(*, persistence_key: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"businesaios:evidence-persistence:{persistence_key}"))

    def _persist_canonical_evidence(
        self,
        *,
        tenant_id: str,
        business_id: str,
        run_id: str,
        step_index: int,
        action_payload: Mapping[str, Any],
        verification_payload: Mapping[str, Any],
        execution_payload: Mapping[str, Any],
        feedback_payload: Mapping[str, Any],
        outcome_record: Mapping[str, Any],
        persistence_key: str,
    ) -> EvidenceRecord | None:
        if self._evidence_store is None:
            return None

        action = dict(action_payload or {})
        verification = dict(verification_payload or {})
        execution = dict(execution_payload or {})
        feedback = dict(feedback_payload or {})
        outcome = dict(outcome_record or {})
        business_outcome = _safe_dict(feedback.get('business_outcome'))
        action_intent = _safe_dict(feedback.get('action_intent'))
        external_refs = tuple(str(item).strip() for item in outcome.get('external_refs') or () if str(item).strip())
        prior_ref_values = action_intent.get('evidence_refs') or action.get('evidence_refs') or business_outcome.get('evidence_refs') or ()
        prior_refs = tuple(str(item).strip() for item in prior_ref_values if str(item).strip())
        refs = tuple(dict.fromkeys((*prior_refs, *external_refs)))
        source = _text(
            business_outcome.get('source_of_truth')
            or _safe_dict(verification.get('verification')).get('source_of_truth')
            or execution.get('source_of_truth')
        ) or 'unknown'
        lineage = {
            'normalization': str(persistence_key),
            'derived_fact': _text(action_intent.get('derived_fact_ref') or action.get('derived_fact_ref') or business_outcome.get('derived_fact_ref')),
            'decision': _text(action_intent.get('decision_id') or action.get('decision_id') or business_outcome.get('decision_id')),
            'action': _text(outcome.get('action_id')),
            'outcome': _text(business_outcome.get('outcome_id')),
        }
        if external_refs:
            lineage['source'] = external_refs[0]
        elif source != 'unknown':
            lineage['source'] = source
        lineage = {key: value for key, value in lineage.items() if value}
        evidence_id = self._canonical_evidence_id(persistence_key=persistence_key)
        created_at = _utc_now()
        existing = self._evidence_store.get(tenant_id=str(tenant_id), evidence_id=evidence_id)
        if existing is not None:
            created_at = existing.created_at
        record = EvidenceRecord(
            evidence_id=evidence_id,
            tenant_id=str(tenant_id),
            scope='closed_loop',
            run_id=str(run_id),
            action_id=_text(outcome.get('action_id')) or None,
            action_type=_text(outcome.get('action_type')) or 'unknown',
            verification_status=_text(outcome.get('verification_status')) or 'unknown',
            created_at=created_at,
            source=source,
            source_type='closed_loop_verification',
            business_id=str(business_id),
            observed_at=None,
            confidence=None,
            privacy_class='internal',
            retention_policy='closed_loop_evidence',
            lineage=lineage,
            refs=refs,
            payload={
                'outcome': outcome,
                **({'action_intent': action_intent} if action_intent else {}),
                **({'business_outcome': business_outcome} if business_outcome else {}),
                'verification': _compact_verification_payload(verification, action=action, execution_receipt=execution),
                'evidence': _compact_evidence_payload(verification),
            },
            labels={
                'business_id': str(business_id),
                'step_index': str(int(step_index)),
                'persistence_key': str(persistence_key),
            },
        ).normalized()
        if existing is not None:
            if existing != record:
                raise ValueError('canonical evidence replay conflicts with persisted evidence')
            return existing
        try:
            return self._evidence_store.append(record)
        except ValueError as exc:
            # Another worker may have won the same idempotent append after our
            # pre-read. Reconcile only the non-semantic creation timestamp; any
            # payload/lineage/scope difference remains a hard conflict.
            current = self._evidence_store.get(tenant_id=str(tenant_id), evidence_id=evidence_id)
            if current is not None:
                replay = replace(record, created_at=current.created_at).normalized()
                if current == replay:
                    return current
            raise ValueError('canonical evidence replay conflicts with persisted evidence') from exc

    def persist(
        self,
        *,
        tenant_id: str,
        business_id: str,
        run_id: str,
        goal: str,
        step_index: int,
        action: Mapping[str, Any],
        execution_result: Mapping[str, Any],
        verification_result: Mapping[str, Any],
        world_state_before: Any,
        world_state_after: Any | None,
        request_meta: Mapping[str, Any] | None = None,
        request_profile: Mapping[str, Any] | None = None,
        request_constraints: Mapping[str, Any] | None = None,
        request_signals: list[dict[str, Any]] | None = None,
        request_channel: str = 'headless',
        request_region: str = 'global',
        request_product_name: str = 'BusinesAIOS',
        completed: bool = False,
        stop_reason: str = '',
        final_feedback: Mapping[str, Any] | None = None,
        step_count: int | None = None,
    ) -> PersistenceArtifacts:
        action_payload = _safe_dict(action)
        verification_payload = _safe_dict(verification_result)
        execution_payload = _safe_dict(execution_result)
        feedback_payload = _safe_dict(final_feedback)

        outcome_record = canonical_persistence_outcome_record(
            base_record={
                'tenant_id': str(tenant_id),
                'business_id': str(business_id),
                'run_id': str(run_id),
                'goal': str(goal),
                'channel': request_channel,
                'region': request_region,
                'completed': bool(completed),
                'stop_reason': str(stop_reason),
                'steps_count': int(step_count or (step_index + 1)),
                'final_feedback': dict(feedback_payload),
            },
            outcome_record={
                'tenant_id': str(tenant_id),
                'business_id': str(business_id),
                'run_id': str(run_id),
                'goal': str(goal),
                'step_index': int(step_index),
                'action_type': _text(action_payload.get('action_type')),
                'action_id': _text(action_payload.get('action_id')),
                'executed': bool(execution_payload.get('executed', execution_payload.get('ok', False))),
                'verified': outcome_is_verified(
                    _safe_dict(verification_payload.get('verification')).get('status') or feedback_payload.get('verification_status'),
                    verified=verification_payload.get('verified'),
                    retryable=_safe_dict(verification_payload.get('verification')).get('retryable'),
                ),
                'verification_status': normalize_outcome_status(
                    _safe_dict(verification_payload.get('verification')).get('status') or feedback_payload.get('verification_status'),
                    verified=verification_payload.get('verified'),
                    retryable=_safe_dict(verification_payload.get('verification')).get('retryable'),
                    default='unknown',
                ),
                'external_refs': _refs_from_verification(verification_payload),
            },
        )
        evidence_records = tuple({
            'tenant_id': str(tenant_id),
            'business_id': str(business_id),
            'run_id': str(run_id),
            'step_index': int(step_index),
            'action_type': outcome_record['action_type'],
            'action_id': outcome_record['action_id'],
            'ref': ref,
        } for ref in outcome_record['external_refs'])
        persistence_key = _persistence_key(
            tenant_id=tenant_id, business_id=business_id, run_id=run_id,
            step_index=step_index, outcome=outcome_record,
        )
        self._persist_canonical_evidence(
            tenant_id=tenant_id, business_id=business_id, run_id=run_id, step_index=step_index,
            action_payload=action_payload, verification_payload=verification_payload,
            execution_payload=execution_payload, feedback_payload=feedback_payload,
            outcome_record=outcome_record, persistence_key=persistence_key,
        )

        memory_record: dict[str, Any] | None = None
        if self._business_memory_store is not None:
            self._business_memory_store.remember_execution(
                tenant_id=tenant_id,
                business_id=business_id,
                run_id=run_id,
                goal=goal,
                completed=bool(completed),
                stop_reason=str(stop_reason),
                final_feedback=dict(feedback_payload),
                step_count=int(step_count or (step_index + 1)),
                profile=dict(request_profile or {}),
                constraints=dict(request_constraints or {}),
                signals=list(request_signals or []),
                meta={**dict(request_meta or {}), 'channel': request_channel, 'region': request_region},
                channel=request_channel,
                region=request_region,
                product_name=request_product_name,
            )
            memory_record = canonical_memory_record(
                tenant_id=str(tenant_id),
                business_id=str(business_id),
                run_id=str(run_id),
                goal=str(goal),
                step_count=int(step_count or (step_index + 1)),
                final_feedback=dict(feedback_payload),
                channel=request_channel,
                region=request_region,
                completed=bool(completed),
                stop_reason=str(stop_reason),
            )
        receipt = {
            'persistence_key': persistence_key,
            'persisted_at': _utc_now().isoformat(),
            'evidence_count': len(evidence_records),
        }
        receipt = self._attach_reliability_receipt(
            tenant_id=tenant_id,
            business_id=business_id,
            run_id=run_id,
            step_index=step_index,
            action_id=_text(outcome_record.get('action_id')),
            action_type=_text(outcome_record.get('action_type')),
            verification_result=verification_payload,
            execution_result=execution_payload,
            receipt=receipt,
        )
        return PersistenceArtifacts(evidence_records=evidence_records, outcome_record=outcome_record, memory_record=memory_record, persistence_receipt=receipt)


def apply_feedback_to_world_state(
    *,
    world_state: Any,
    verification_result: Mapping[str, Any] | None,
    receipt: Mapping[str, Any] | None = None,
) -> Any:
    compact_outcome = _compact_verification_payload(verification_result)
    compact_evidence = _compact_evidence_payload(verification_result)
    resolved_receipt = dict(receipt or {
        'persistence_key': _persistence_key(outcome=compact_outcome),
        'persisted_at': _utc_now().isoformat(),
    })
    return _apply_feedback_world_state(
        world_state=world_state,
        compact_outcome=compact_outcome,
        compact_evidence=compact_evidence,
        receipt=resolved_receipt,
    )


__all__ = [
    'CANON_EVIDENCE_PERSISTENCE',
    'EvidencePersistenceService',
    'PersistenceArtifacts',
    'apply_feedback_to_world_state',
]
