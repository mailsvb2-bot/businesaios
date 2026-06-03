from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from collections.abc import Mapping

from runtime.monetization.revenue_advisory_contracts import RevenueDecisionEnvelope, RevenueExperimentSurface

CANON_RUNTIME_MONETIZATION_REVENUE_ADVISORY_STORE = True


class RevenueAppendOnlyStore(Protocol):
    def append(self, record: dict[str, Any]) -> None: ...


@dataclass(frozen=True, slots=True)
class RegisteredRevenueExperiment:
    dedup_key: str
    experiment: RevenueExperimentSurface


@dataclass
class JsonlAppendOnlyStore:
    path: Path

    def append(self, record: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(dict(record), ensure_ascii=False, sort_keys=True)
        with self.path.open('a', encoding='utf-8') as fh:
            fh.write(line + '\n')


@dataclass
class FileRevenueExperimentRegistry:
    path: Path = Path('.runtime_data/revenue_os/experiments.json')

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding='utf-8'))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _save(self, data: dict[str, dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + '.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
        os.replace(tmp, self.path)

    def get(self, dedup_key: str) -> RegisteredRevenueExperiment | None:
        normalized = str(dedup_key or '').strip()
        if not normalized:
            return None
        payload = self._load().get(normalized)
        if not isinstance(payload, dict):
            return None
        surface = self._surface_from_payload(payload.get('experiment'))
        if surface is None:
            return None
        return RegisteredRevenueExperiment(dedup_key=normalized, experiment=surface)

    def put_if_absent(self, *, dedup_key: str, experiment: RevenueExperimentSurface) -> RegisteredRevenueExperiment:
        normalized = str(dedup_key or '').strip()
        if not normalized:
            raise ValueError('dedup_key is required')
        data = self._load()
        existing = data.get(normalized)
        if isinstance(existing, dict):
            surface = self._surface_from_payload(existing.get('experiment'))
            if surface is not None:
                return RegisteredRevenueExperiment(dedup_key=normalized, experiment=surface)
        registered = RegisteredRevenueExperiment(dedup_key=normalized, experiment=self._normalized_surface(experiment))
        data[normalized] = {'dedup_key': normalized, 'experiment': self._surface_to_payload(registered.experiment)}
        self._save(data)
        return registered

    def _surface_to_payload(self, surface: RevenueExperimentSurface) -> dict[str, Any]:
        return {
            'experiment_id': surface.experiment_id,
            'kind': surface.kind,
            'hypothesis': surface.hypothesis,
            'metric_primary': surface.metric_primary,
            'metric_guardrails': list(surface.metric_guardrails),
            'arms': [dict(arm) for arm in surface.arms],
            'holdout_allocation': float(surface.holdout_allocation),
            'max_daily_exposure': int(surface.max_daily_exposure),
            'created_at': surface.created_at,
            'metadata': dict(surface.metadata),
        }

    def _surface_from_payload(self, payload: object) -> RevenueExperimentSurface | None:
        if not isinstance(payload, dict):
            return None
        try:
            return self._normalized_surface(
                RevenueExperimentSurface(
                    experiment_id=str(payload.get('experiment_id') or ''),
                    kind=str(payload.get('kind') or ''),
                    hypothesis=str(payload.get('hypothesis') or ''),
                    metric_primary=str(payload.get('metric_primary') or ''),
                    metric_guardrails=tuple(str(item) for item in payload.get('metric_guardrails') or ()),
                    arms=tuple(dict(item) for item in payload.get('arms') or ()),
                    holdout_allocation=float(payload.get('holdout_allocation') or 0.0),
                    max_daily_exposure=int(payload.get('max_daily_exposure') or 0),
                    created_at=str(payload.get('created_at') or ''),
                    metadata=dict(payload.get('metadata') or {}),
                )
            )
        except Exception:
            return None

    def _normalized_surface(self, surface: RevenueExperimentSurface) -> RevenueExperimentSurface:
        return RevenueExperimentSurface(
            experiment_id=str(surface.experiment_id).strip(),
            kind=str(surface.kind).strip(),
            hypothesis=str(surface.hypothesis).strip(),
            metric_primary=str(surface.metric_primary).strip(),
            metric_guardrails=tuple(str(item).strip() for item in surface.metric_guardrails),
            arms=tuple(dict(item) for item in surface.arms),
            holdout_allocation=float(surface.holdout_allocation),
            max_daily_exposure=max(0, int(surface.max_daily_exposure)),
            created_at=str(surface.created_at or ''),
            metadata=dict(surface.metadata),
        )


@dataclass(frozen=True)
class RevenueAdvisoryStoreWiring:
    experiment_registry: FileRevenueExperimentRegistry
    audit_store: RevenueAppendOnlyStore
    evidence_store: RevenueAppendOnlyStore
    telemetry_store: RevenueAppendOnlyStore


def build_revenue_advisory_store_wiring(*, root_dir: str | Path | None = None) -> RevenueAdvisoryStoreWiring:
    root = Path(root_dir) if root_dir is not None else Path('.runtime_data/revenue_os')
    return RevenueAdvisoryStoreWiring(
        experiment_registry=FileRevenueExperimentRegistry(path=root / 'experiments.json'),
        audit_store=JsonlAppendOnlyStore(path=root / 'audit.jsonl'),
        evidence_store=JsonlAppendOnlyStore(path=root / 'evidence.jsonl'),
        telemetry_store=JsonlAppendOnlyStore(path=root / 'telemetry.jsonl'),
    )



def _dedup_key(*, tenant_id: str, product_id: str, experiment_id: str) -> str:
    return "::".join((str(tenant_id).strip(), str(product_id).strip(), str(experiment_id).strip()))


def persist_revenue_advisory_envelope(
    *,
    wiring: RevenueAdvisoryStoreWiring,
    tenant_id: str,
    product_id: str,
    envelope: RevenueDecisionEnvelope,
) -> dict[str, int]:
    explain = dict(envelope.explain or {})
    if str(explain.get('mode') or '').strip().lower() != 'advisory_only':
        raise ValueError('revenue advisory envelope must remain advisory_only')
    owner = str(explain.get('owner') or '').strip()
    if owner != 'runtime.monetization.revenue_advisory':
        raise ValueError('revenue advisory envelope owner drift detected')

    audit_count = 0
    for record in envelope.audit_records:
        wiring.audit_store.append(dict(record))
        audit_count += 1

    registered = 0
    for item in envelope.experiments:
        dedup_key = _dedup_key(tenant_id=tenant_id, product_id=product_id, experiment_id=item.experiment_id)
        existing = wiring.experiment_registry.get(dedup_key)
        if existing is None:
            wiring.experiment_registry.put_if_absent(dedup_key=dedup_key, experiment=item)
            registered += 1

    summary = dict(explain.get('summary') or {})
    telemetry_payload = {
        'tenant_id': str(tenant_id),
        'product_id': str(product_id),
        'owner': owner,
        'mode': 'advisory_only',
        'metrics': summary,
        'experiments_count': len(envelope.experiments),
        'candidate_actions_count': len(envelope.candidate_actions),
    }
    wiring.evidence_store.append(
        {
            'tenant_id': str(tenant_id),
            'product_id': str(product_id),
            'owner': owner,
            'world_state_patch': dict(envelope.world_state_patch),
            'candidate_actions': [
                {
                    'action_type': item.action_type,
                    'kind': item.kind,
                    'confidence': item.confidence,
                    'payload': dict(item.payload),
                    'evidence': dict(item.evidence),
                    'reason_codes': list(item.reason_codes),
                    'blast_radius': item.blast_radius,
                    'requires_approval': item.requires_approval,
                    'owner': item.owner,
                }
                for item in envelope.candidate_actions
            ],
            'experiments': [
                {
                    'experiment_id': item.experiment_id,
                    'kind': item.kind,
                    'hypothesis': item.hypothesis,
                    'metric_primary': item.metric_primary,
                    'metric_guardrails': list(item.metric_guardrails),
                    'arms': [dict(arm) for arm in item.arms],
                    'holdout_allocation': item.holdout_allocation,
                    'max_daily_exposure': item.max_daily_exposure,
                    'created_at': item.created_at,
                    'metadata': dict(item.metadata),
                }
                for item in envelope.experiments
            ],
        }
    )
    wiring.telemetry_store.append(telemetry_payload)
    return {
        'audit_records': audit_count,
        'evidence_records': 1,
        'telemetry_records': 1,
        'registered_experiments': registered,
    }


__all__ = [
    'CANON_RUNTIME_MONETIZATION_REVENUE_ADVISORY_STORE',
    'FileRevenueExperimentRegistry',
    'JsonlAppendOnlyStore',
    'RegisteredRevenueExperiment',
    'RevenueAdvisoryStoreWiring',
    'persist_revenue_advisory_envelope',
    'RevenueAppendOnlyStore',
    'build_revenue_advisory_store_wiring',
]
