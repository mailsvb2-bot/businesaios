from __future__ import annotations

import hashlib
from typing import Any

from contracts.event_store import BUSINESS_FACT_EVENT_TYPE, BusinessFactV1
from reliability.idempotency_contract import IdempotencyResolution, IdempotencyState, IdempotencyStore
from reliability.idempotency_scope import build_idempotency_key

CANON_ONTOLOGY_EVENT_FACT_MUTATION = True


class EventFactLifecycleWriter:
    """Shared durable mutation primitive for canonical ontology entities.

    It owns no entity semantics and no storage. It only guarantees that one
    semantic mutation maps to one BusinessFactV1 plus one idempotency claim.
    """

    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore, namespace: str, source: str, id_prefix: str) -> None:
        self._events = event_store
        self._claims = idempotency_store
        self._namespace = str(namespace).strip()
        self._source = str(source).strip()
        self._id_prefix = str(id_prefix).strip()
        if not all((self._namespace, self._source, self._id_prefix)):
            raise ValueError("ontology mutation identity is required")

    def _scope(self, *, tenant_id: str, business_id: str, entity_id: str, operation: str, idempotency_key: str, payload: dict[str, object]):
        key = str(idempotency_key or "").strip()
        if not key:
            raise ValueError("idempotency_key is required")
        scope = build_idempotency_key(
            tenant_id=str(tenant_id), namespace=self._namespace, operation=str(operation), key=key,
            semantic_scope={"business_id": str(business_id), "entity_id": str(entity_id), "payload": dict(payload)},
        )
        raw = "\0".join((str(tenant_id), str(business_id), str(entity_id), str(operation), key, str(scope.scope_hash))).encode("utf-8")
        return key, scope, f"{self._id_prefix}:{hashlib.sha256(raw).hexdigest()}"

    def _find(self, *, tenant_id: str, fact_id: str) -> dict[str, Any] | None:
        for event in self._events.iter_events(tenant_id=str(tenant_id), start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE):
            if str(event.get("event_id") or "") == str(fact_id):
                return dict(event)
        return None

    def _assert_match(self, event: dict[str, Any], *, business_id: str, entity_id: str, fact_type: str, payload: dict[str, object]) -> None:
        envelope = dict(event.get("payload") or {})
        if not (
            str(event.get("source") or "") == self._source
            and str(envelope.get("business_id") or "") == str(business_id)
            and str(envelope.get("fact_type") or "") == str(fact_type)
            and str(envelope.get("entity_id") or "") == str(entity_id)
            and dict(envelope.get("payload") or {}) == dict(payload)
        ):
            raise ValueError("ontology durable fact conflicts with requested mutation")

    def repair_existing(self, *, tenant_id: str, business_id: str, entity_id: str, operation: str, idempotency_key: str, fact_type: str, payload: dict[str, object]) -> bool:
        _, scope, fact_id = self._scope(tenant_id=tenant_id, business_id=business_id, entity_id=entity_id, operation=operation, idempotency_key=idempotency_key, payload=payload)
        event = self._find(tenant_id=tenant_id, fact_id=fact_id)
        if event is None:
            return False
        self._assert_match(event, business_id=business_id, entity_id=entity_id, fact_type=fact_type, payload=payload)
        owner_id = f"ontology-fact:{fact_id}"
        record = self._claims.get(key=scope)
        if record is None:
            raise RuntimeError("ontology durable fact has no idempotency claim")
        if not record.idempotency_key.same_scope(scope):
            raise RuntimeError("ontology durable fact idempotency scope mismatch")
        if record.state is IdempotencyState.COMPLETED:
            if record.result_ref != fact_id or record.result_digest not in {None, str(scope.scope_hash)}:
                raise RuntimeError("ontology completed claim conflicts with durable fact")
            return True
        if record.state is IdempotencyState.FAILED:
            raise RuntimeError("ontology durable fact has terminal failed idempotency claim")
        if str(record.owner_id or "") != owner_id:
            raise RuntimeError("ontology durable fact idempotency owner mismatch")
        if not record.has_live_lease():
            decision = self._claims.reserve(key=scope, owner_id=owner_id, lease_ttl_seconds=300)
            if decision.resolution is IdempotencyResolution.REPLAY_COMPLETED:
                if decision.replay_result_ref != fact_id:
                    raise RuntimeError("ontology replay claim points to a different fact")
                return True
            if decision.resolution is not IdempotencyResolution.ACCEPTED:
                raise RuntimeError(f"ontology recovery rejected: {decision.resolution.value}")
        self._claims.mark_completed(key=scope, owner_id=owner_id, result_ref=fact_id, result_digest=str(scope.scope_hash))
        return True

    def append_once(self, *, tenant_id: str, business_id: str, entity_id: str, operation: str, idempotency_key: str, fact_type: str, payload: dict[str, object], occurred_at_ms: int) -> str:
        _, scope, fact_id = self._scope(tenant_id=tenant_id, business_id=business_id, entity_id=entity_id, operation=operation, idempotency_key=idempotency_key, payload=payload)
        if self.repair_existing(tenant_id=tenant_id, business_id=business_id, entity_id=entity_id, operation=operation, idempotency_key=idempotency_key, fact_type=fact_type, payload=payload):
            return fact_id
        owner_id = f"ontology-fact:{fact_id}"
        decision = self._claims.reserve(key=scope, owner_id=owner_id, lease_ttl_seconds=300)
        if decision.resolution is IdempotencyResolution.REPLAY_COMPLETED:
            raise RuntimeError("ontology idempotency claim completed without durable fact")
        if decision.resolution is not IdempotencyResolution.ACCEPTED:
            raise RuntimeError(f"ontology mutation rejected: {decision.resolution.value}")
        event = BusinessFactV1(
            fact_id=fact_id, tenant_id=str(tenant_id), business_id=str(business_id), fact_type=str(fact_type), entity_id=str(entity_id),
            event_time_ms=int(occurred_at_ms), observed_at_ms=int(occurred_at_ms), source=self._source, payload=dict(payload),
        ).as_event()
        try:
            self._events.append_event(event)
        except Exception:
            durable = self._find(tenant_id=tenant_id, fact_id=fact_id)
            if durable is None:
                raise
            self._assert_match(durable, business_id=business_id, entity_id=entity_id, fact_type=fact_type, payload=payload)
        durable = self._find(tenant_id=tenant_id, fact_id=fact_id)
        if durable is None:
            raise RuntimeError("ontology EventStore append did not become durable")
        self._assert_match(durable, business_id=business_id, entity_id=entity_id, fact_type=fact_type, payload=payload)
        self._claims.mark_completed(key=scope, owner_id=owner_id, result_ref=fact_id, result_digest=str(scope.scope_hash))
        return fact_id


__all__ = ["CANON_ONTOLOGY_EVENT_FACT_MUTATION", "EventFactLifecycleWriter"]
