from __future__ import annotations

from typing import Any
from collections.abc import Mapping

CANON_SCENARIO_GOVERNANCE_CONTRACT = True


def _text(value: Any) -> str:
    return str(value or '').strip()


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _safe_bool(value: Any) -> bool:
    return bool(value)


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def canonical_scenario_namespace(*, scenario: str, baseline_name: str = '', prefix: str = 'scenario', suffix: str = 'golden') -> dict[str, Any]:
    normalized_scenario = _text(scenario).lower().replace(' ', '_')
    resolved_baseline_name = _text(baseline_name or f'{prefix}:{normalized_scenario}:{suffix}')
    return {
        'scenario_governance': {
            'scenario': _text(scenario),
            'normalized_scenario': normalized_scenario,
            'namespace_prefix': _text(prefix),
            'namespace_suffix': _text(suffix),
            'baseline_name': resolved_baseline_name,
        }
    }


def canonical_scenario_catalog_entry(
    *,
    scenario: str,
    baseline_name: str,
    source_run_id: str,
    metadata: Mapping[str, Any] | None = None,
    prefix: str = 'scenario',
    suffix: str = 'golden',
    existing_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    existing = _safe_dict(existing_payload)
    merged_metadata = {**_safe_dict(existing.get('metadata')), **_safe_dict(metadata)}
    scenario_governance = canonical_scenario_namespace(
        scenario=scenario or existing.get('scenario'),
        baseline_name=baseline_name or existing.get('baseline_name'),
        prefix=prefix,
        suffix=suffix,
    )
    return {
        'scenario': _text(scenario or existing.get('scenario')),
        'baseline_name': _text(baseline_name or existing.get('baseline_name')),
        'source_run_id': _text(source_run_id or existing.get('source_run_id')),
        'metadata': merged_metadata,
        'scenario_governance': {
            **dict(scenario_governance.get('scenario_governance') or {}),
            'source_run_id': _text(source_run_id or existing.get('source_run_id')),
            'metadata': merged_metadata,
        },
    }



def canonical_scenario_selection_outcome(
    *,
    scenario: str,
    baseline_name: str,
    selected_record: Mapping[str, Any] | None,
    governance_decision: Mapping[str, Any] | None = None,
    catalog_entry: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    record = _safe_dict(selected_record)
    decision = _safe_dict(governance_decision).get('governance_decision') if isinstance(_safe_dict(governance_decision).get('governance_decision'), Mapping) else _safe_dict(governance_decision)
    entry = _safe_dict(catalog_entry).get('scenario_governance') if isinstance(_safe_dict(catalog_entry).get('scenario_governance'), Mapping) else _safe_dict(catalog_entry)
    merged_metadata = {**_safe_dict(entry.get('metadata')), **_safe_dict(metadata)}
    return {
        'scenario_governance': {
            'scenario': _text(scenario or entry.get('scenario')),
            'baseline_name': _text(baseline_name or entry.get('baseline_name')),
            'selected_run_id': _text(record.get('run_id') or decision.get('selected_run_id') or entry.get('source_run_id')),
            'goal': _text(record.get('goal')),
            'tenant_id': _text(record.get('tenant_id')),
            'business_id': _text(record.get('business_id')),
            'approved': _safe_bool(decision.get('approved') if decision else record),
            'confidence': _safe_float(decision.get('confidence') if decision else _safe_dict(record.get('final_feedback')).get('goal_score')),
            'reasons': [str(x) for x in _safe_list(decision.get('reasons') if decision else []) if str(x)],
            'summary': _text(decision.get('summary') if decision else 'scenario_selection_recorded'),
            'catalog_entry': _safe_dict(entry),
            'governance_decision': _safe_dict(decision),
            'metadata': merged_metadata,
        }
    }


__all__ = [
    'CANON_SCENARIO_GOVERNANCE_CONTRACT',
    'canonical_scenario_catalog_entry',
    'canonical_scenario_namespace',
    'canonical_scenario_selection_outcome',
]
