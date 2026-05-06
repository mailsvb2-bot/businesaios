from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping

from reliability.execution_checkpoint_store import ExecutionCheckpoint
from reliability.idempotency_contract import IdempotencyKey, IdempotencyResolution
from reliability.outbox_store import OutboxMessage, canonical_payload_digest

from application.effects.effect_outcome_vocabulary import outcome_is_verified

CANON_EVIDENCE_PERSISTENCE_RELIABILITY = True


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _text(value: object) -> str:
    return str(value or '').strip()


@dataclass(slots=True)
class EvidencePersistenceReliabilitySupport:
    checkpoint_store: Any | None = None
    idempotency_store: Any | None = None
    outbox_store: Any | None = None
    replay_guard: Any | None = None
    reconciliation_service: Any | None = None
    tenant_default: str = 'system'
    reliability_namespace: str = 'evidence_persistence'
    reliability_operation: str = 'persist_feedback'
    idempotency_owner_id: str = 'evidence-persistence'

    def tenant_id(self, *, tenant_id: str = '') -> str:
        normalized = str(tenant_id or self.tenant_default).strip() or self.tenant_default
        if not normalized:
            raise ValueError('tenant_id must not be empty')
        return normalized

    def idempotency_key(self, *, tenant_id: str, business_id: str, run_id: str, step_index: int, persistence_key: str) -> IdempotencyKey:
        scope_seed = f"{tenant_id}::{business_id}::{run_id}::{step_index}::{persistence_key}"
        return IdempotencyKey(
            tenant_id=self.tenant_id(tenant_id=tenant_id),
            namespace=self.reliability_namespace,
            operation=self.reliability_operation,
            key=str(persistence_key),
            scope_hash=hashlib.sha256(scope_seed.encode('utf-8')).hexdigest(),
        )

    def checkpoint(self, *, tenant_id: str, run_id: str, stage: str, checkpoint_id: str, idempotency_key: str, payload: Mapping[str, Any] | None = None, outbox_message_id: str | None = None, action_id: str | None = None) -> None:
        if self.checkpoint_store is None:
            return
        latest = None
        try:
            latest = self.checkpoint_store.latest(tenant_id=self.tenant_id(tenant_id=tenant_id), run_id=str(run_id))
        except Exception:
            latest = None
        next_sequence = 0 if latest is None else int(getattr(latest, 'sequence_no', -1)) + 1
        self.checkpoint_store.append(
            ExecutionCheckpoint(
                tenant_id=self.tenant_id(tenant_id=tenant_id),
                run_id=str(run_id),
                sequence_no=next_sequence,
                stage=str(stage),
                checkpoint_id=str(checkpoint_id),
                action_id=None if action_id is None else str(action_id),
                idempotency_key=str(idempotency_key),
                outbox_message_id=None if outbox_message_id is None else str(outbox_message_id),
                payload=dict(payload or {}),
            )
        )

    def effect_topic(self, *, action_type: str, verification_result: Mapping[str, Any], execution_result: Mapping[str, Any]) -> str:
        verified = outcome_is_verified(
            _safe_dict(verification_result.get('verification')).get('status'),
            verified=verification_result.get('verified'),
            retryable=_safe_dict(verification_result.get('verification')).get('retryable'),
        )
        executed = bool(execution_result.get('executed', execution_result.get('ok', False)))
        if executed and verified and str(action_type or '').strip():
            return f"execution.effect.{str(action_type).strip()}"
        return 'execution.evidence_persisted'

    def enqueue_outbox(self, *, tenant_id: str, message_id: str, dedupe_key: str, payload: Mapping[str, Any], topic: str = 'execution.evidence_persisted', run_id: str | None = None, effect_key: str | None = None, effect_kind: str | None = None) -> OutboxMessage | None:
        if self.outbox_store is None:
            return None
        resolved_payload = dict(payload)
        message = OutboxMessage(
            tenant_id=self.tenant_id(tenant_id=tenant_id),
            message_id=str(message_id),
            topic=str(topic),
            dedupe_key=str(dedupe_key),
            payload=resolved_payload,
            run_id=None if run_id is None else str(run_id),
            payload_digest=canonical_payload_digest(resolved_payload),
            effect_key=None if effect_key is None else str(effect_key),
            effect_kind=None if effect_kind is None else str(effect_kind),
        )
        return self.outbox_store.enqueue(message)

    def try_reserve_idempotency(self, *, key: IdempotencyKey) -> tuple[bool, str, Any | None]:
        if self.idempotency_store is None:
            return True, 'disabled', None
        decision = self.idempotency_store.reserve(key=key, owner_id=self.idempotency_owner_id)
        return decision.resolution is IdempotencyResolution.ACCEPTED, decision.resolution.value, decision

    def mark_idempotency_completed(self, *, key: IdempotencyKey, result_ref: str) -> None:
        if self.idempotency_store is None:
            return
        self.idempotency_store.mark_completed(
            key=key,
            owner_id=self.idempotency_owner_id,
            result_ref=str(result_ref),
            result_digest=str(result_ref),
        )

    def mark_idempotency_failed(self, *, key: IdempotencyKey, reason: str, logger: Any | None = None) -> None:
        if self.idempotency_store is None:
            return
        try:
            self.idempotency_store.mark_failed(key=key, owner_id=self.idempotency_owner_id, reason=str(reason))
        except Exception as exc:
            if logger is not None:
                logger.warning('evidence_persistence_mark_failed_failed', exc_info=exc)

    def replay_detected(self, *, tenant_id: str, run_id: str, persistence_key: str) -> bool:
        if self.replay_guard is None or not hasattr(self.replay_guard, 'is_replay'):
            return False
        try:
            return bool(self.replay_guard.is_replay(tenant_id=self.tenant_id(tenant_id=tenant_id), run_id=str(run_id), persistence_key=str(persistence_key)))
        except TypeError:
            try:
                return bool(self.replay_guard.is_replay(str(persistence_key)))
            except Exception:
                return False
        except Exception:
            return False

    def reconciliation_summary(self, *, tenant_id: str, run_id: str, idempotency_key: IdempotencyKey, outbox_message_id: str) -> dict[str, Any] | None:
        if self.reconciliation_service is None:
            return None
        report = self.reconciliation_service.reconcile(
            tenant_id=self.tenant_id(tenant_id=tenant_id),
            run_id=str(run_id),
            idempotency_key=idempotency_key,
            outbox_message_id=str(outbox_message_id),
        )
        return {
            'latest_stage': getattr(report, 'latest_stage', None),
            'is_clean': bool(getattr(report, 'is_clean', False)),
            'anomalies': list(getattr(report, 'anomalies', ()) or ()),
            'outbox_state': getattr(report, 'outbox_state', None),
            'idempotency_state': getattr(report, 'idempotency_state', None),
        }

    def attach_reliability_receipt(self, *, tenant_id: str, business_id: str, run_id: str, step_index: int, action_id: str, action_type: str = '', verification_result: Mapping[str, Any] | None = None, execution_result: Mapping[str, Any] | None = None, receipt: dict[str, Any], logger: Any | None = None) -> dict[str, Any]:
        persistence_key = str(receipt.get('persistence_key') or '')
        if not persistence_key:
            return dict(receipt)
        updated = dict(receipt)
        outbox_message_id = f"evidence:{run_id}:{step_index}:{persistence_key[:12]}"
        updated['outbox_message_id'] = outbox_message_id
        updated['effect_key'] = persistence_key
        updated['delivery_guarantee'] = 'exactly_once_effect_scope'
        replay_detected = self.replay_detected(tenant_id=tenant_id, run_id=run_id, persistence_key=persistence_key)
        updated['replay_detected'] = replay_detected
        key = self.idempotency_key(tenant_id=tenant_id, business_id=business_id, run_id=run_id, step_index=step_index, persistence_key=persistence_key)
        updated['idempotency_key'] = key.key
        updated['reliability_enabled'] = any(item is not None for item in (self.checkpoint_store, self.idempotency_store, self.outbox_store))
        if replay_detected:
            updated['replayed'] = True
            updated['idempotency_resolution'] = 'replay_detected'
            updated['reconciliation'] = self.reconciliation_summary(tenant_id=tenant_id, run_id=run_id, idempotency_key=key, outbox_message_id=outbox_message_id)
            return updated
        accepted, resolution, _decision = self.try_reserve_idempotency(key=key)
        updated['idempotency_resolution'] = resolution
        if not accepted:
            updated['replayed'] = True
            updated['reconciliation'] = self.reconciliation_summary(tenant_id=tenant_id, run_id=run_id, idempotency_key=key, outbox_message_id=outbox_message_id)
            return updated
        try:
            self.checkpoint(
                tenant_id=tenant_id,
                run_id=run_id,
                stage='evidence',
                checkpoint_id=f'evidence:{persistence_key[:16]}',
                idempotency_key=key.key,
                outbox_message_id=outbox_message_id,
                action_id=action_id,
                payload={'persistence_key': persistence_key, 'phase': 'persisted'},
            )
            outbox_message = self.enqueue_outbox(
                tenant_id=tenant_id,
                message_id=outbox_message_id,
                dedupe_key=persistence_key,
                payload={
                    'tenant_id': self.tenant_id(tenant_id=tenant_id),
                    'business_id': str(business_id),
                    'run_id': str(run_id),
                    'step_index': int(step_index),
                    'persistence_key': persistence_key,
                    'action_id': str(action_id),
                    'action_type': str(action_type),
                    'verification_status': str(_safe_dict(verification_result or {}).get('verification', {}).get('status') or ''),
                    'effect_key': persistence_key,
                },
                topic=self.effect_topic(action_type=str(action_type), verification_result=_safe_dict(verification_result), execution_result=_safe_dict(execution_result)),
                run_id=str(run_id),
                effect_key=persistence_key,
                effect_kind='effect_receipt' if str(action_type).strip() else 'evidence_receipt',
            )
            updated['outbox_state'] = None if outbox_message is None else outbox_message.state.value
            updated['outbox_topic'] = None if outbox_message is None else outbox_message.topic
            updated['outbox_payload_digest'] = None if outbox_message is None else outbox_message.resolved_payload_digest
            updated['outbox_backend_name'] = None if outbox_message is None else outbox_message.backend_name
            updated['outbox_external_id'] = None if outbox_message is None else outbox_message.external_id
            updated['outbox_delivered_at'] = None if outbox_message is None or outbox_message.delivered_at is None else outbox_message.delivered_at.isoformat()
            updated['outbox_delivery_metadata'] = {} if outbox_message is None else dict(outbox_message.delivery_metadata)
            runtime_delivery = _safe_dict(_safe_dict(execution_result).get('effect_delivery'))
            if runtime_delivery:
                updated['runtime_effect_delivery'] = runtime_delivery
            self.mark_idempotency_completed(key=key, result_ref=persistence_key)
            self.checkpoint(
                tenant_id=tenant_id,
                run_id=run_id,
                stage='completed',
                checkpoint_id=f'completed:{persistence_key[:16]}',
                idempotency_key=key.key,
                outbox_message_id=outbox_message_id,
                action_id=action_id,
                payload={'persistence_key': persistence_key, 'phase': 'committed'},
            )
        except Exception as exc:
            self.mark_idempotency_failed(key=key, reason=f'evidence_persistence:{type(exc).__name__}', logger=logger)
            self.checkpoint(
                tenant_id=tenant_id,
                run_id=run_id,
                stage='failed',
                checkpoint_id=f'failed:{persistence_key[:16]}',
                idempotency_key=key.key,
                outbox_message_id=outbox_message_id,
                action_id=action_id,
                payload={'persistence_key': persistence_key, 'reason': type(exc).__name__},
            )
            raise
        updated['reconciliation'] = self.reconciliation_summary(tenant_id=tenant_id, run_id=run_id, idempotency_key=key, outbox_message_id=outbox_message_id)
        return updated


__all__ = ['CANON_EVIDENCE_PERSISTENCE_RELIABILITY', 'EvidencePersistenceReliabilitySupport']
