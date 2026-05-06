from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

CANON_ECONOMIC_SEMANTIC_VALIDATION = True

CANON_ECONOMIC_CAUSAL_CHAIN = (
    'budget_guard',
    'execution',
    'verification',
    'revenue',
    'memory',
)


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_rows(value: object) -> list[dict[str, Any]]:
    return [_safe_dict(item) for item in value or ()]


def _text(value: object) -> str:
    return str(value or '').strip()


def _extract_chain_id(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = _text(row.get(key))
        if value:
            return value
    return ''


@dataclass(frozen=True, slots=True)
class EconomicSemanticValidationVerdict:
    valid: bool
    violations: tuple[str, ...] = ()
    reason: str = 'economic_semantics_valid'
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'valid': bool(self.valid),
            'violations': list(self.violations),
            'reason': self.reason,
            'metadata': dict(self.metadata),
        }


class EconomicSemanticValidator:
    def validate(self, *, payload: Mapping[str, Any]) -> EconomicSemanticValidationVerdict:
        normalized = _safe_dict(payload)
        violations: list[str] = []

        feedback_rows = _safe_rows(normalized.get('feedback_rows'))
        roi_rows = _safe_rows(normalized.get('roi_rows'))
        trace_rows = _safe_rows(normalized.get('trace_rows'))
        metrics_rows = _safe_rows(normalized.get('metrics_rows'))
        manifest = _safe_dict(normalized.get('export_manifest'))
        metadata = _safe_dict(normalized.get('metadata'))

        feedback_event_ids = {
            _extract_chain_id(x, 'event_id', 'memory_key', 'action_id')
            for x in feedback_rows
            if _extract_chain_id(x, 'event_id', 'memory_key', 'action_id')
        }
        roi_event_ids = {
            _extract_chain_id(x, 'event_id', 'memory_key', 'action_id')
            for x in roi_rows
            if _extract_chain_id(x, 'event_id', 'memory_key', 'action_id')
        }
        trace_ids = {str(x.get('trace_id') or '') for x in trace_rows if x.get('trace_id')}
        trace_event_ids = {
            _extract_chain_id(x, 'event_id', 'action_id', 'decision_id', 'run_id')
            for x in trace_rows
            if _extract_chain_id(x, 'event_id', 'action_id', 'decision_id', 'run_id')
        }
        metric_snapshot_ids = {str(x.get('snapshot_id') or '') for x in metrics_rows if x.get('snapshot_id')}

        if roi_event_ids and not (roi_event_ids & feedback_event_ids):
            violations.append('roi_feedback_disconnected')

        if (feedback_rows or roi_rows) and not trace_ids:
            violations.append('missing_trace_rows')

        if metrics_rows and not metric_snapshot_ids:
            violations.append('metrics_snapshot_ids_missing')


        causal_chain = _safe_dict(normalized.get('causal_chain'))
        chain_sources = [_safe_dict(source) for source in normalized.get('causal_chain_sources') or ()]
        if not causal_chain and chain_sources:
            merged: dict[str, Any] = {}
            for source in chain_sources:
                merged.update(source)
            causal_chain = merged
        if not causal_chain:
            causal_chain = _safe_dict(metadata.get('causal_chain'))
        if not causal_chain:
            causal_chain = _safe_dict(manifest.get('causal_chain'))

        if causal_chain:
            missing_steps = [step for step in CANON_ECONOMIC_CAUSAL_CHAIN if not _safe_dict(causal_chain.get(step))]
            if missing_steps:
                violations.append('causal_chain_step_missing')

            extracted_ids = {
                step: _extract_chain_id(_safe_dict(causal_chain.get(step)), 'event_id', 'action_id', 'decision_id', 'run_id', 'snapshot_id')
                for step in CANON_ECONOMIC_CAUSAL_CHAIN
            }
            non_empty_ids = {value for value in extracted_ids.values() if value}
            if len(non_empty_ids) > 1:
                violations.append('causal_chain_id_mismatch')

            budget_guard = _safe_dict(causal_chain.get('budget_guard'))
            verification = _safe_dict(causal_chain.get('verification'))
            revenue = _safe_dict(causal_chain.get('revenue'))
            memory = _safe_dict(causal_chain.get('memory'))
            if budget_guard and _text(budget_guard.get('status')).lower() in {'denied', 'blocked', 'rejected'}:
                if verification or revenue or memory:
                    violations.append('causal_chain_budget_guard_bypass')
            if verification and _text(verification.get('status')).lower() in {'failed', 'invalid', 'rejected'}:
                if revenue or memory:
                    violations.append('causal_chain_verification_bypass')

            revenue_refs = {
                _extract_chain_id(revenue, 'event_id', 'action_id', 'decision_id', 'run_id'),
                _text(revenue.get('trace_id')),
            } - {''}
            if revenue_refs and trace_ids and not (revenue_refs & (trace_ids | trace_event_ids)):
                violations.append('causal_chain_revenue_trace_disconnected')

            memory_ref = _extract_chain_id(memory, 'event_id', 'memory_key', 'action_id', 'decision_id', 'run_id')
            if memory_ref and feedback_event_ids and memory_ref not in feedback_event_ids and memory_ref not in roi_event_ids and memory_ref not in trace_event_ids:
                violations.append('causal_chain_memory_unanchored')

        return EconomicSemanticValidationVerdict(
            valid=not violations,
            violations=tuple(dict.fromkeys(violations)),
            reason='economic_semantics_valid' if not violations else 'economic_semantics_invalid',
            metadata={
                'owner': 'execution.economic_semantic_validation',
                'causal_chain_checked': bool(causal_chain),
                'trace_count': len(trace_rows),
            },
        )


__all__ = [
    'CANON_ECONOMIC_SEMANTIC_VALIDATION',
    'CANON_ECONOMIC_CAUSAL_CHAIN',
    'EconomicSemanticValidationVerdict',
    'EconomicSemanticValidator',
]
