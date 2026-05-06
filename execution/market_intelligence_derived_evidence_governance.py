from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from typing import Any, Mapping


CANON_MARKET_INTELLIGENCE_DERIVED_EVIDENCE_GOVERNANCE = True


def _text(value: object, *, default: str = '') -> str:
    text = str(value or '').strip()
    return text or default


@dataclass(frozen=True)
class RawEvidenceRef:
    provider: str
    source_family: str
    external_id: str
    observed_at: str | None = None
    checksum: str | None = None


@dataclass(frozen=True)
class DerivedEvidenceEnvelope:
    evidence_id: str
    tenant_id: str
    derived_kind: str
    policy_name: str
    confidence: float
    raw_refs: tuple[RawEvidenceRef, ...]
    explainability: Mapping[str, Any]
    payload: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            'evidence_id': self.evidence_id,
            'tenant_id': self.tenant_id,
            'derived_kind': self.derived_kind,
            'policy_name': self.policy_name,
            'confidence': self.confidence,
            'raw_refs': [ref.__dict__ for ref in self.raw_refs],
            'explainability': dict(self.explainability),
            'payload': dict(self.payload),
        }


@dataclass(frozen=True)
class DerivationPolicy:
    policy_name: str = 'market_intelligence_derived_evidence_v1'
    min_confidence: float = 0.60
    allow_hidden_ranking_heuristics: bool = False
    max_raw_refs: int = 32

    def validate(self, *, confidence: float, ranking_policy_name: str | None) -> None:
        if float(confidence) < float(self.min_confidence):
            raise ValueError('derived evidence confidence below policy threshold')
        if not self.allow_hidden_ranking_heuristics and not _text(ranking_policy_name):
            raise ValueError('hidden ranking heuristics are forbidden')

    def assert_not_decision_payload(self, payload: Mapping[str, Any]) -> None:
        forbidden = {'decision', 'decision_core', 'chosen_action', 'plan_override', 'decide'}
        normalized = {str(k).lower() for k in dict(payload or {}).keys()}
        hit = sorted(forbidden & normalized)
        if hit:
            raise ValueError(f'derived evidence must not embed decision-path fields: {hit}')


@dataclass
class MarketIntelligenceDerivedEvidenceGovernance:
    policy: DerivationPolicy = field(default_factory=DerivationPolicy)

    def build(self, *, tenant_id: str, derived_kind: str, confidence: float, raw_records: list[Mapping[str, Any]], payload: Mapping[str, Any], ranking_policy_name: str, explainability: Mapping[str, Any]) -> DerivedEvidenceEnvelope:
        self.policy.validate(confidence=confidence, ranking_policy_name=ranking_policy_name)
        self.policy.assert_not_decision_payload(payload)
        refs: list[RawEvidenceRef] = []
        for row in raw_records[: self.policy.max_raw_refs]:
            refs.append(RawEvidenceRef(provider=_text(row.get('provider')), source_family=_text(row.get('source_family')), external_id=_text(row.get('external_id')), observed_at=_text(row.get('observed_at')) or None, checksum=self._row_checksum(row)))
        evidence_id = hashlib.sha256(f"{tenant_id}|{derived_kind}|{ranking_policy_name}|{repr(sorted((ref.provider, ref.external_id) for ref in refs))}".encode('utf-8')).hexdigest()
        return DerivedEvidenceEnvelope(
            evidence_id=evidence_id,
            tenant_id=_text(tenant_id, default='default'),
            derived_kind=_text(derived_kind),
            policy_name=self.policy.policy_name,
            confidence=max(0.0, min(float(confidence), 1.0)),
            raw_refs=tuple(refs),
            explainability={'ranking_policy_name': ranking_policy_name, 'raw_support_count': len(refs), **dict(explainability or {})},
            payload=dict(payload or {}),
        )

    def _row_checksum(self, row: Mapping[str, Any]) -> str:
        return hashlib.sha256(repr(sorted(dict(row).items())).encode('utf-8')).hexdigest()
