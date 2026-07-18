from __future__ import annotations

from hashlib import sha256
from dataclasses import dataclass, field, replace
from datetime import datetime
import json
from typing import Mapping, Protocol
from uuid import uuid4

from billing.commercial_cycle_contract import utc_now
from billing.dispute_policy import DisputeClassification, DisputePolicy
from billing.lineage import derive_lineage_metadata
from core.tenancy.normalization import require_tenant_id
from observability.tenant_metrics_registry import TenantMetricsRegistry
from runtime.platform.billing_dispute_store import DISPUTE_SCHEMA_VERSION, PlatformSqliteDisputeStore


CANON_BILLING_DISPUTE_ORCHESTRATOR = True


@dataclass(frozen=True)
class DisputeCase:
    tenant_id: str
    invoice_id: str
    case_id: str
    classification: DisputeClassification
    status: str = 'open'
    idempotency_key: str | None = None
    opened_at: datetime = field(default_factory=utc_now)
    resolved_at: datetime | None = None
    resolution: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.invoice_id or '').strip():
            raise ValueError('invoice_id is required')
        if not str(self.case_id or '').strip():
            raise ValueError('case_id is required')
        self.classification.validate()
        normalized_status = str(self.status or '').strip().lower()
        if normalized_status not in {'open', 'resolved', 'rejected', 'escalated'}:
            raise ValueError('status must be open, resolved, rejected, or escalated')
        if self.opened_at.tzinfo is None:
            raise ValueError('opened_at must be timezone-aware')
        if self.resolved_at is not None and self.resolved_at.tzinfo is None:
            raise ValueError('resolved_at must be timezone-aware')
        if normalized_status != 'open' and self.resolution is None:
            raise ValueError('non-open dispute case requires resolution')
        if normalized_status == 'open' and self.resolved_at is not None:
            raise ValueError('open dispute case cannot have resolved_at')
        if self.idempotency_key is not None and not str(self.idempotency_key).strip():
            raise ValueError('idempotency_key cannot be blank')
        evidence_fingerprint = str(dict(self.metadata).get('evidence_fingerprint') or '').strip()
        if not evidence_fingerprint:
            raise ValueError('evidence_fingerprint is required')


class DisputeStoreContract(Protocol):
    def save(self, case: DisputeCase, *, idempotency_key: str | None = None) -> DisputeCase: ...
    def get_by_idempotency(self, *, tenant_id: str, invoice_id: str, idempotency_key: str) -> DisputeCase | None: ...
    def get(self, *, tenant_id: str, case_id: str) -> DisputeCase | None: ...
    def list_for_invoice(self, *, tenant_id: str, invoice_id: str) -> tuple[DisputeCase, ...]: ...


class InMemoryDisputeStore:
    def __init__(self) -> None:
        self._by_case: dict[tuple[str, str], DisputeCase] = {}
        self._by_invoice: dict[tuple[str, str], tuple[DisputeCase, ...]] = {}
        self._by_idempotency: dict[tuple[str, str, str], DisputeCase] = {}

    def save(self, case: DisputeCase, *, idempotency_key: str | None = None) -> DisputeCase:
        case.validate()
        tid = require_tenant_id(case.tenant_id)
        cid = str(case.case_id).strip()
        iid = str(case.invoice_id).strip()
        idem = None if idempotency_key is None else (str(idempotency_key).strip() or None)
        if idem:
            existing = self._by_idempotency.get((tid, iid, idem))
            if existing is not None:
                if existing == case:
                    return existing
                if existing.case_id != case.case_id or existing.invoice_id != case.invoice_id:
                    raise ValueError('dispute idempotency collision')
        existing_case = self._by_case.get((tid, cid))
        if existing_case is not None and existing_case != case:
            if existing_case.invoice_id != case.invoice_id:
                raise ValueError('dispute case_id collision')
        self._by_case[(tid, cid)] = case
        invoice_key = (tid, iid)
        current = [item for item in self._by_invoice.get(invoice_key, ()) if item.case_id != cid]
        current.append(case)
        self._by_invoice[invoice_key] = tuple(sorted(current, key=lambda item: (item.opened_at.isoformat(), item.case_id)))
        if idem:
            self._by_idempotency[(tid, iid, idem)] = case
        return case

    def get_by_idempotency(self, *, tenant_id: str, invoice_id: str, idempotency_key: str) -> DisputeCase | None:
        return self._by_idempotency.get((require_tenant_id(tenant_id), str(invoice_id).strip(), str(idempotency_key).strip()))

    def get(self, *, tenant_id: str, case_id: str) -> DisputeCase | None:
        return self._by_case.get((require_tenant_id(tenant_id), str(case_id).strip()))

    def list_for_invoice(self, *, tenant_id: str, invoice_id: str) -> tuple[DisputeCase, ...]:
        return tuple(self._by_invoice.get((require_tenant_id(tenant_id), str(invoice_id).strip()), ()))


class SqliteDisputeStore(PlatformSqliteDisputeStore):
    """Billing-facing dispute store facade.

    SQLite ownership lives in runtime.platform.billing_dispute_store.
    """

    def __init__(self, *, sqlite_path: str) -> None:
        super().__init__(sqlite_path=sqlite_path, case_cls=DisputeCase)


class DisputeOrchestrator:
    def __init__(self, *, policy: DisputePolicy | None = None, store: DisputeStoreContract | None = None, metrics: TenantMetricsRegistry | None = None) -> None:
        self._policy = policy or DisputePolicy()
        self._store = store or InMemoryDisputeStore()
        self._metrics = metrics

    def open_case(
        self,
        *,
        tenant_id: str,
        invoice_id: str,
        payload: Mapping[str, object],
        idempotency_key: str | None = None,
        opened_at: datetime | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> DisputeCase:
        tid = require_tenant_id(tenant_id)
        iid = str(invoice_id).strip()
        idem = None if idempotency_key is None else (str(idempotency_key).strip() or None)
        if not iid:
            raise ValueError('invoice_id is required')
        evidence_fingerprint = self._payload_fingerprint(payload)
        if idem:
            existing = self._store.get_by_idempotency(tenant_id=tid, invoice_id=iid, idempotency_key=idem)
            if existing is not None:
                if str(dict(existing.metadata).get('evidence_fingerprint') or '') != evidence_fingerprint:
                    raise ValueError('dispute idempotency fingerprint mismatch')
                return existing
        classification = self._policy.classify(payload)
        observed_at = opened_at or utc_now()
        if observed_at.tzinfo is None:
            raise ValueError('opened_at must be timezone-aware')
        case = DisputeCase(
            tenant_id=tid,
            invoice_id=iid,
            case_id=f'dsp_{uuid4().hex[:20]}',
            classification=classification,
            status='open',
            idempotency_key=idem,
            opened_at=observed_at,
            metadata=derive_lineage_metadata(
                invoice_id=iid,
                invoice_metadata=metadata,
                event_type='dispute',
                event_id=f"dispute:{idem or 'open'}",
                idempotency_key=idem,
                extra={**dict(metadata or {}), 'owner': 'billing.dispute_orchestrator', 'payload': dict(payload), 'evidence_fingerprint': evidence_fingerprint},
            ),
        )
        case.validate()
        saved = self._store.save(case, idempotency_key=idem)
        if self._metrics is not None:
            self._metrics.inc(tenant_id=tid, metric_name='billing_dispute_cases_total', amount=1.0, labels={'case_type': classification.case_type, 'severity': classification.severity})
        return saved

    def resolve_case(self, *, case: DisputeCase, resolution: str, status: str = 'resolved', resolved_at: datetime | None = None, metadata: Mapping[str, object] | None = None) -> DisputeCase:
        case.validate()
        if str(case.status).strip().lower() != 'open':
            raise ValueError('only open dispute cases can transition')
        normalized_status = str(status or '').strip().lower()
        if normalized_status not in {'resolved', 'rejected', 'escalated'}:
            raise ValueError('resolution status must be resolved, rejected, or escalated')
        normalized_resolution = str(resolution or '').strip()
        if not normalized_resolution:
            raise ValueError('resolution is required')
        observed_at = resolved_at or utc_now()
        if observed_at.tzinfo is None:
            raise ValueError('resolved_at must be timezone-aware')
        updated = replace(
            case,
            status=normalized_status,
            resolved_at=observed_at,
            resolution=normalized_resolution,
            metadata=derive_lineage_metadata(invoice_id=case.invoice_id, invoice_metadata=case.metadata, event_type='dispute', event_id=case.case_id, idempotency_key=case.idempotency_key, extra={**dict(metadata or {}), 'owner': 'billing.dispute_orchestrator'}),
        )
        updated.validate()
        saved = self._store.save(updated, idempotency_key=updated.idempotency_key)
        if self._metrics is not None:
            self._metrics.inc(tenant_id=case.tenant_id, metric_name='billing_dispute_resolutions_total', amount=1.0, labels={'status': normalized_status, 'severity': updated.classification.severity})
        return saved

    def reject_case(self, *, case: DisputeCase, resolution: str, resolved_at: datetime | None = None, metadata: Mapping[str, object] | None = None) -> DisputeCase:
        return self.resolve_case(case=case, resolution=resolution, status='rejected', resolved_at=resolved_at, metadata=metadata)

    def escalate_case(self, *, case: DisputeCase, resolution: str, resolved_at: datetime | None = None, metadata: Mapping[str, object] | None = None) -> DisputeCase:
        return self.resolve_case(case=case, resolution=resolution, status='escalated', resolved_at=resolved_at, metadata=metadata)

    @staticmethod
    def _payload_fingerprint(payload: Mapping[str, object]) -> str:
        canonical = json.dumps(dict(payload or {}), sort_keys=True, separators=(',', ':'), default=str)
        return sha256(canonical.encode('utf-8')).hexdigest()


__all__ = [
    'CANON_BILLING_DISPUTE_ORCHESTRATOR',
    'DISPUTE_SCHEMA_VERSION',
    'DisputeCase',
    'DisputeOrchestrator',
    'DisputeStoreContract',
    'InMemoryDisputeStore',
    'SqliteDisputeStore',
]
