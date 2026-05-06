from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass, field
import re
from typing import Any, Dict, Mapping

from config.environment_matrix import normalize_environment_name
from core.tenancy.normalization import normalize_tenant_id
from governance.persistence_codec import to_jsonable


CANONICAL_OBJECTIVE_NAME = 'profit_adjusted_growth'
CANONICAL_FLOW = (
    'signal',
    'opportunity',
    'decision',
    'execution',
    'feedback',
    'strategy',
)
_SECTION_NAME_RE = re.compile(r'^[a-z0-9_]+$')


@dataclass(frozen=True)
class OptimizationObjective:
    name: str = CANONICAL_OBJECTIVE_NAME
    maximize: bool = True
    risk_penalty_weight: float = 1.0
    confidence_penalty_weight: float = 0.5

    def validate(self) -> None:
        if self.name != CANONICAL_OBJECTIVE_NAME:
            raise ValueError(f'non-canonical optimization objective: {self.name}')
        if self.risk_penalty_weight < 0.0:
            raise ValueError('risk_penalty_weight must be >= 0')
        if self.confidence_penalty_weight < 0.0:
            raise ValueError('confidence_penalty_weight must be >= 0')


@dataclass(frozen=True)
class RuntimeLimits:
    max_budget_delta: float = 0.20
    min_confidence: float = 0.60
    max_risk_score: float = 0.75

    def validate(self) -> None:
        if self.max_budget_delta < 0.0:
            raise ValueError('max_budget_delta must be >= 0')
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError('min_confidence must be between 0 and 1')
        if not 0.0 <= self.max_risk_score <= 1.0:
            raise ValueError('max_risk_score must be between 0 and 1')


@dataclass
class ConfigSection:
    values: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def require(self, key: str) -> Any:
        normalized_key = str(key or '').strip()
        if normalized_key not in self.values:
            raise KeyError(f'missing config key: {normalized_key}')
        return self.values[normalized_key]

    def merge(self, mapping: Mapping[str, Any]) -> None:
        self.values.update(to_jsonable(dict(mapping or {})))

    def normalized(self) -> 'ConfigSection':
        normalized_values = {
            str(key).strip(): to_jsonable(value)
            for key, value in dict(self.values).items()
            if str(key).strip()
        }
        return ConfigSection(values=normalized_values)

    def validate(self) -> None:
        for key in self.values:
            if not str(key or '').strip():
                raise ValueError('config section keys must be non-empty')

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return dict(self.normalized().values)


@dataclass
class SystemConfig:
    objective: OptimizationObjective = field(default_factory=OptimizationObjective)
    limits: RuntimeLimits = field(default_factory=RuntimeLimits)
    sections: Dict[str, ConfigSection] = field(default_factory=dict)
    environment: str = 'dev'
    tenant_id: str | None = None
    labels: Dict[str, str] = field(default_factory=dict)

    def section(self, name: str) -> ConfigSection:
        normalized = self._normalize_section_name(name)
        if normalized not in self.sections:
            self.sections[normalized] = ConfigSection()
        return self.sections[normalized]

    def merge_section(self, name: str, mapping: Mapping[str, Any]) -> None:
        self.section(name).merge(mapping)

    def normalized(self) -> 'SystemConfig':
        normalized_sections = {
            self._normalize_section_name(name): section.normalized()
            for name, section in dict(self.sections).items()
        }
        normalized = SystemConfig(
            objective=self.objective,
            limits=self.limits,
            sections=normalized_sections,
            environment=normalize_environment_name(self.environment),
            tenant_id=normalize_tenant_id(self.tenant_id) or None,
            labels={str(key).strip(): str(value).strip() for key, value in dict(self.labels).items() if str(key).strip() and str(value).strip()},
        )
        normalized.validate()
        return normalized

    def execution_contract(self) -> dict[str, Any]:
        normalized = self.normalized()
        return {
            'objective_name': normalized.objective.name,
            'canonical_flow': list(CANONICAL_FLOW),
            'environment': normalized.environment,
            'tenant_id': normalized.tenant_id,
            'limits': {
                'max_budget_delta': normalized.limits.max_budget_delta,
                'min_confidence': normalized.limits.min_confidence,
                'max_risk_score': normalized.limits.max_risk_score,
            },
        }

    def validate(self) -> None:
        self.objective.validate()
        self.limits.validate()
        if not normalize_environment_name(self.environment):
            raise ValueError('environment must not be empty')
        for name, section in dict(self.sections).items():
            if self._normalize_section_name(name) != name:
                raise ValueError(f'non-normalized section name: {name}')
            section.validate()
        for key in self.labels:
            if not str(key or '').strip():
                raise ValueError('labels must use non-empty keys')

    def to_dict(self) -> dict[str, Any]:
        normalized = self.normalized()
        return {
            'objective': {
                'name': normalized.objective.name,
                'maximize': normalized.objective.maximize,
                'risk_penalty_weight': normalized.objective.risk_penalty_weight,
                'confidence_penalty_weight': normalized.objective.confidence_penalty_weight,
            },
            'limits': {
                'max_budget_delta': normalized.limits.max_budget_delta,
                'min_confidence': normalized.limits.min_confidence,
                'max_risk_score': normalized.limits.max_risk_score,
            },
            'sections': {name: section.to_dict() for name, section in normalized.sections.items()},
            'environment': normalized.environment,
            'tenant_id': normalized.tenant_id,
            'labels': dict(normalized.labels),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> 'SystemConfig':
        rows = dict(payload or {})
        objective_payload = dict(rows.get('objective') or {})
        limits_payload = dict(rows.get('limits') or {})
        sections_payload = dict(rows.get('sections') or {})
        config = cls(
            objective=OptimizationObjective(
                name=str(objective_payload.get('name') or CANONICAL_OBJECTIVE_NAME),
                maximize=bool(objective_payload.get('maximize', True)),
                risk_penalty_weight=float(objective_payload.get('risk_penalty_weight', 1.0)),
                confidence_penalty_weight=float(objective_payload.get('confidence_penalty_weight', 0.5)),
            ),
            limits=RuntimeLimits(
                max_budget_delta=float(limits_payload.get('max_budget_delta', 0.20)),
                min_confidence=float(limits_payload.get('min_confidence', 0.60)),
                max_risk_score=float(limits_payload.get('max_risk_score', 0.75)),
            ),
            sections={
                cls._normalize_section_name(name): ConfigSection(values=to_jsonable(dict(value or {})))
                for name, value in sections_payload.items()
            },
            environment=normalize_environment_name(str(rows.get('environment') or 'dev')),
            tenant_id=normalize_tenant_id(rows.get('tenant_id')) or None,
            labels={str(key).strip(): str(value).strip() for key, value in dict(rows.get('labels') or {}).items() if str(key).strip() and str(value).strip()},
        )
        config.validate()
        return config

    @staticmethod
    def _normalize_section_name(name: str) -> str:
        normalized = str(name or '').strip().lower().replace(' ', '_')
        if not normalized:
            raise ValueError('section name must not be empty')
        if not _SECTION_NAME_RE.match(normalized):
            raise ValueError(f'invalid section name: {name}')
        return normalized


__all__ = [
    'CANONICAL_FLOW',
    'CANONICAL_OBJECTIVE_NAME',
    'ConfigSection',
    'OptimizationObjective',
    'RuntimeLimits',
    'SystemConfig',
]
