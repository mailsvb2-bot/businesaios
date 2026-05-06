from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone

from ..action_context import SafetyActionContext
from ..action_identity import stable_payload

CANON_SAFETY_SIMULATION_EVIDENCE = True
_DEFAULT_SECRET = 'businesaios-simulation-evidence-dev-secret'
_DEFAULT_KEY_ID = 'sim-default'


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _evidence_payload(payload: dict[str, object]) -> dict[str, object]:
    raw = dict(payload or {})
    dropped_exact = {
        'simulation_score', 'simulation_provenance', 'simulation_verified', 'simulation_signature',
        'simulation_artifact_fingerprint', 'simulation_model_fingerprint', 'simulation_expires_at',
        'expected_reward', 'expected_margin', 'approval_id', 'worker_id', 'executor_id', 'runtime_owner',
    }
    return {
        str(key): value
        for key, value in raw.items()
        if not str(key).startswith('simulation_') and str(key) not in dropped_exact
    }


def _parse_ts(value: str) -> datetime | None:
    text = str(value or '').strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00'))
    except Exception:
        return None


@dataclass(frozen=True)
class SimulationEvidence:
    score: float
    provenance: str
    verified: bool
    signature: str = ''
    artifact_fingerprint: str = ''
    model_fingerprint: str = ''
    expires_at: str = ''
    key_id: str = ''
    dataset_fingerprint: str = ''


class SimulationEvidenceVerifier:
    def __init__(self, *, secret: str | None = None) -> None:
        self._secret_text = str(secret or os.getenv('BUSINESAIOS_SIMULATION_EVIDENCE_SECRET') or _DEFAULT_SECRET)
        self._secret = self._secret_text.encode('utf-8')
        self._key_id = str(os.getenv('BUSINESAIOS_SIMULATION_EVIDENCE_KEY_ID') or _DEFAULT_KEY_ID).strip() or _DEFAULT_KEY_ID

    @property
    def using_insecure_fallback(self) -> bool:
        return self._secret_text == _DEFAULT_SECRET

    def sign(self, *, ctx: SafetyActionContext, score: float, provenance: str, artifact_fingerprint: str = '', model_fingerprint: str = '', expires_at: str = '', dataset_fingerprint: str = '') -> str:
        resolved_artifact_fingerprint = str(artifact_fingerprint or self.payload_fingerprint(ctx))
        resolved_dataset_fingerprint = str(dataset_fingerprint or self.dataset_fingerprint(ctx))
        material = self._material(ctx=ctx, score=score, provenance=provenance, artifact_fingerprint=resolved_artifact_fingerprint, model_fingerprint=model_fingerprint, expires_at=expires_at, dataset_fingerprint=resolved_dataset_fingerprint)
        return hmac.new(self._secret, material, hashlib.sha256).hexdigest()

    def verify(self, *, ctx: SafetyActionContext, evidence: SimulationEvidence) -> bool:
        if not evidence.verified:
            return False
        if not str(evidence.provenance).strip():
            return False
        signature = str(evidence.signature or '').strip()
        if not signature:
            return False
        expires_at = _parse_ts(evidence.expires_at)
        if expires_at is not None and expires_at <= _now_utc():
            return False
        expected_fingerprint = self.payload_fingerprint(ctx)
        if evidence.artifact_fingerprint and evidence.artifact_fingerprint != expected_fingerprint:
            return False
        expected = self.sign(
            ctx=ctx,
            score=float(evidence.score),
            provenance=str(evidence.provenance),
            artifact_fingerprint=str(evidence.artifact_fingerprint or expected_fingerprint),
            model_fingerprint=str(evidence.model_fingerprint or ''),
            expires_at=str(evidence.expires_at or ''),
            dataset_fingerprint=str(evidence.dataset_fingerprint or self.dataset_fingerprint(ctx)),
        )
        return hmac.compare_digest(signature, expected)

    def payload_fingerprint(self, ctx: SafetyActionContext) -> str:
        return hashlib.sha256(json.dumps(stable_payload(_evidence_payload(dict(ctx.payload))), sort_keys=True, default=str).encode('utf-8')).hexdigest()

    def dataset_fingerprint(self, ctx: SafetyActionContext) -> str:
        payload = dict(ctx.payload)
        dataset = payload.get('simulation_dataset_fingerprint') or payload.get('dataset_fingerprint') or payload.get('training_dataset_fingerprint') or ''
        return hashlib.sha256(str(dataset).encode('utf-8')).hexdigest() if str(dataset) else ''

    def from_payload(self, ctx: SafetyActionContext) -> SimulationEvidence:
        payload = dict(ctx.payload)
        score = float(payload.get('simulation_score', -1.0) or -1.0)
        provenance = str(payload.get('simulation_provenance') or '').strip()
        verified = bool(payload.get('simulation_verified'))
        signature = str(payload.get('simulation_signature') or '').strip()
        artifact_fingerprint = str(payload.get('simulation_artifact_fingerprint') or self.payload_fingerprint(ctx)).strip()
        model_fingerprint = str(payload.get('simulation_model_fingerprint') or '').strip()
        expires_at = str(payload.get('simulation_expires_at') or '').strip()
        key_id = str(payload.get('simulation_key_id') or self._key_id).strip()
        dataset_fingerprint = str(payload.get('simulation_dataset_fingerprint') or self.dataset_fingerprint(ctx)).strip()
        candidate = SimulationEvidence(
            score=score,
            provenance=provenance,
            verified=verified,
            signature=signature,
            artifact_fingerprint=artifact_fingerprint,
            model_fingerprint=model_fingerprint,
            expires_at=expires_at,
            key_id=key_id,
            dataset_fingerprint=dataset_fingerprint,
        )
        if signature:
            verified = self.verify(ctx=ctx, evidence=SimulationEvidence(**{**candidate.__dict__, 'verified': True}))
            candidate = SimulationEvidence(**{**candidate.__dict__, 'verified': verified})
        return candidate

    @staticmethod
    def _material(*, ctx: SafetyActionContext, score: float, provenance: str, artifact_fingerprint: str, model_fingerprint: str, expires_at: str, dataset_fingerprint: str) -> bytes:
        payload = {
            'tenant_id': str(ctx.tenant_id),
            'action': str(ctx.action),
            'payload': stable_payload(_evidence_payload(dict(ctx.payload))),
            'simulation_score': float(score),
            'simulation_provenance': str(provenance),
            'simulation_artifact_fingerprint': str(artifact_fingerprint),
            'simulation_model_fingerprint': str(model_fingerprint),
            'simulation_expires_at': str(expires_at),
            'simulation_dataset_fingerprint': str(dataset_fingerprint),
        }
        return json.dumps(payload, sort_keys=True, default=str).encode('utf-8')


__all__ = ['CANON_SAFETY_SIMULATION_EVIDENCE', 'SimulationEvidence', 'SimulationEvidenceVerifier']
