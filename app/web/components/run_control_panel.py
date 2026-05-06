from __future__ import annotations

"""Operator run control panel.

Strictly read-only / intent-only UI surface for canonical run state.
This module does not execute actions or decide policy.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Mapping

from core.tenancy.normalization import normalize_tenant_id, require_tenant_id
from security.payload_redaction import PayloadRedactor
from shared.kinded_payloads import build_kinded_payload


CANON_WEB_RUN_CONTROL_PANEL = True
_MAX_CONTROLS = 32
_MAX_EVENTS = 500
_ALLOWED_CONTROL_CODES = frozenset(
    {
        'pause',
        'resume',
        'cancel',
        'retry',
        'recover',
        'quarantine',
        'open_trace',
        'open_audit',
        'open_dead_letter',
        'open_recovery',
    }
)
_TERMINAL_STATUSES = frozenset({'completed', 'failed', 'cancelled', 'dead_letter'})


def _safe_int(value: Any, *, default: int = 0, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def _text(value: Any) -> str:
    return str(value or '').strip()


def _enum_text(value: Any) -> str:
    return _text(getattr(value, 'value', value))


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    text = _text(value)
    return text or None


def _mapping_copy(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(k): v for k, v in value.items()}


def _risk_flags_tuple(value: Any) -> tuple[str, ...]:
    return tuple(sorted({_text(item) for item in tuple(value or ()) if _text(item)}))


def _normalize_control(item: Any) -> dict[str, Any] | None:
    if isinstance(item, Mapping):
        code = _text(item.get('code'))
        if not code or code not in _ALLOWED_CONTROL_CODES:
            return None
        return {
            'code': code,
            'label': _text(item.get('label')) or code.replace('_', ' ').title(),
            'enabled': _safe_bool(item.get('enabled', True)),
            'operator_required': _safe_bool(item.get('operator_required', True)),
            'confirmation_required': _safe_bool(item.get('confirmation_required', True)),
            'reason': _text(item.get('reason')) or None,
            'href': _text(item.get('href')) or None,
            'metadata': _mapping_copy(item.get('metadata')),
        }
    code = _text(item)
    if not code or code not in _ALLOWED_CONTROL_CODES:
        return None
    return {
        'code': code,
        'label': code.replace('_', ' ').title(),
        'enabled': True,
        'operator_required': True,
        'confirmation_required': True,
        'reason': None,
        'href': None,
        'metadata': {},
    }


def _normalize_event(item: Any) -> dict[str, Any]:
    if isinstance(item, Mapping):
        return {
            'tenant_id': _text(item.get('tenant_id')),
            'trace_id': _text(item.get('trace_id')) or None,
            'run_id': _text(item.get('run_id')) or None,
            'sequence_no': _safe_int(item.get('sequence_no'), default=0, minimum=0),
            'stage': _text(item.get('stage')),
            'event_type': _text(item.get('event_type')),
            'emitted_at': _iso(item.get('emitted_at')),
            'summary': _text(item.get('summary')) or None,
            'component': _text(item.get('component')) or None,
            'payload': _mapping_copy(item.get('payload')),
        }
    return {
        'tenant_id': _text(getattr(item, 'tenant_id', '')),
        'trace_id': _text(getattr(item, 'trace_id', '')) or None,
        'run_id': _text(getattr(item, 'run_id', '')) or None,
        'sequence_no': _safe_int(getattr(item, 'sequence_no', 0), default=0, minimum=0),
        'stage': _enum_text(getattr(item, 'stage', '')),
        'event_type': _text(getattr(item, 'event_type', '')),
        'emitted_at': _iso(getattr(item, 'emitted_at', None)),
        'summary': _text(getattr(item, 'summary', '')) or None,
        'component': _text(getattr(item, 'component', '')) or None,
        'payload': _mapping_copy(getattr(item, 'payload', {})),
    }


def _normalize_run(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'tenant_id': _text(item.get('tenant_id')),
        'run_id': _text(item.get('run_id')),
        'trace_id': _text(item.get('trace_id')) or None,
        'decision_id': _text(item.get('decision_id')) or None,
        'action_id': _text(item.get('action_id')) or None,
        'goal': _text(item.get('goal')) or None,
        'status': _text(item.get('status')) or 'unknown',
        'stage': _text(item.get('stage')) or None,
        'started_at': _iso(item.get('started_at')),
        'updated_at': _iso(item.get('updated_at')),
        'completed_at': _iso(item.get('completed_at')),
        'operator_locked': _safe_bool(item.get('operator_locked', False)),
        'human_approval_required': _safe_bool(item.get('human_approval_required', False)),
        'canary': _safe_bool(item.get('canary', False)),
        'owner_id': _text(item.get('owner_id')) or None,
        'isolation_slot_id': _text(item.get('isolation_slot_id')) or None,
        'risk_flags': _risk_flags_tuple(item.get('risk_flags')),
        'metadata': _mapping_copy(item.get('metadata')),
    }


@dataclass(frozen=True, slots=True)
class RunControlPanel:
    payload_redactor: PayloadRedactor = field(default_factory=PayloadRedactor)
    kind: str = 'run_control_panel'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))

        run = _normalize_run(_mapping_copy(normalized.get('run')))
        run_tenant_id = normalize_tenant_id(run.get('tenant_id'))
        if run_tenant_id and run_tenant_id != tenant_id:
            raise ValueError('run tenant_id does not match panel tenant_id')
        run['tenant_id'] = tenant_id
        if not str(run.get('run_id') or '').strip():
            raise ValueError('run.run_id is required')

        controls: list[dict[str, Any]] = []
        seen_control_codes: set[str] = set()
        for item in tuple(normalized.get('controls', ()) or ()):
            row = _normalize_control(item)
            if row is None:
                continue
            code = str(row['code'])
            if code in seen_control_codes:
                continue
            seen_control_codes.add(code)
            controls.append(row)
            if len(controls) >= _MAX_CONTROLS:
                break
        controls.sort(key=lambda row: (not bool(row['enabled']), str(row['code'])))

        events: list[dict[str, Any]] = []
        seen_event_keys: set[tuple[str, int, str]] = set()
        for item in tuple(normalized.get('recent_events', ()) or ()):
            row = _normalize_event(item)
            row_tenant_id = normalize_tenant_id(row.get('tenant_id'))
            if row_tenant_id and row_tenant_id != tenant_id:
                continue
            row['tenant_id'] = tenant_id
            key = (
                str(row.get('trace_id') or row.get('run_id') or ''),
                _safe_int(row.get('sequence_no'), default=0, minimum=0),
                str(row.get('event_type') or ''),
            )
            if key in seen_event_keys:
                continue
            seen_event_keys.add(key)
            events.append(row)
            if len(events) >= _MAX_EVENTS:
                break
        events.sort(key=lambda row: (_safe_int(row.get('sequence_no'), default=0, minimum=0), str(row.get('emitted_at') or ''), str(row.get('event_type') or '')))

        recovery = _mapping_copy(normalized.get('recovery'))
        if recovery:
            recovery = {
                'run_id': _text(recovery.get('run_id')) or None,
                'recovery_action': _text(recovery.get('recovery_action')) or None,
                'reason': _text(recovery.get('reason')) or None,
                'delivery_hint': _text(recovery.get('delivery_hint')) or None,
                'dead_letter_hint': _text(recovery.get('dead_letter_hint')) or None,
                'operator_required': _safe_bool(recovery.get('operator_required', False)),
                'operator_hint': _text(recovery.get('operator_hint')) or None,
                'resume_action': _text(recovery.get('resume_action')) or None,
                'resume_stage': _text(recovery.get('resume_stage')) or None,
                'anomaly_count': _safe_int(recovery.get('anomaly_count'), default=0, minimum=0),
                'risk_flags': _risk_flags_tuple(recovery.get('risk_flags')),
                'policy_snapshot': _mapping_copy(recovery.get('policy_snapshot')),
            }

        status = str(run.get('status') or '').strip().lower()
        result = {
            'tenant_id': tenant_id,
            'title': 'Run Control',
            'run': run,
            'controls': tuple(controls),
            'recent_events': tuple(events),
            'recovery': recovery or None,
            'summary': {
                'enabled_control_count': sum(1 for row in controls if bool(row.get('enabled'))),
                'disabled_control_count': sum(1 for row in controls if not bool(row.get('enabled'))),
                'event_count': len(events),
                'risk_flag_count': len(tuple(run.get('risk_flags') or ())),
                'has_recovery_attention': bool(recovery and (bool(recovery.get('operator_required')) or _safe_int(recovery.get('anomaly_count'), default=0, minimum=0) > 0 or bool(tuple(recovery.get('risk_flags') or ())))),
                'is_terminal': status in _TERMINAL_STATUSES,
                'has_human_gate': bool(run.get('human_approval_required')),
                'operator_locked': bool(run.get('operator_locked')),
            },
            'tenant_bound': True,
            'read_only': True,
            'control_intent_only': True,
        }
        return build_kinded_payload(self.kind, self.payload_redactor.redact(result))

    def build_from_snapshot(
        self,
        *,
        tenant_id: str,
        run_snapshot: Any,
        allowed_controls: Iterable[Any] = (),
        recent_events: Iterable[Any] = (),
        recovery_plan: Any | None = None,
    ) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        run = {
            'tenant_id': required_tenant_id,
            'run_id': _text(getattr(run_snapshot, 'run_id', '')),
            'trace_id': _text(getattr(run_snapshot, 'trace_id', '')) or None,
            'decision_id': _text(getattr(run_snapshot, 'decision_id', '')) or None,
            'action_id': _text(getattr(run_snapshot, 'action_id', '')) or None,
            'goal': _text(getattr(run_snapshot, 'goal', '')) or None,
            'status': _enum_text(getattr(run_snapshot, 'status', '')) or 'unknown',
            'stage': _enum_text(getattr(run_snapshot, 'stage', '')) or None,
            'started_at': _iso(getattr(run_snapshot, 'started_at', None)),
            'updated_at': _iso(getattr(run_snapshot, 'updated_at', None)),
            'completed_at': _iso(getattr(run_snapshot, 'completed_at', None)),
            'operator_locked': _safe_bool(getattr(run_snapshot, 'operator_locked', False)),
            'human_approval_required': _safe_bool(getattr(run_snapshot, 'human_approval_required', False)),
            'canary': _safe_bool(getattr(run_snapshot, 'canary', False)),
            'owner_id': _text(getattr(run_snapshot, 'owner_id', '')) or None,
            'isolation_slot_id': _text(getattr(run_snapshot, 'isolation_slot_id', '')) or None,
            'risk_flags': _risk_flags_tuple(getattr(run_snapshot, 'risk_flags', ()) or ()),
            'metadata': _mapping_copy(getattr(run_snapshot, 'metadata', {})),
        }
        recovery = None
        if recovery_plan is not None:
            recovery = {
                'run_id': _text(getattr(recovery_plan, 'run_id', '')) or None,
                'recovery_action': _text(getattr(recovery_plan, 'recovery_action', '')) or None,
                'reason': _text(getattr(recovery_plan, 'reason', '')) or None,
                'delivery_hint': _text(getattr(recovery_plan, 'delivery_hint', '')) or None,
                'dead_letter_hint': _text(getattr(recovery_plan, 'dead_letter_hint', '')) or None,
                'operator_required': _safe_bool(getattr(recovery_plan, 'operator_required', False)),
                'operator_hint': _text(getattr(recovery_plan, 'operator_hint', '')) or None,
                'resume_action': _text(getattr(recovery_plan, 'resume_action', '')) or None,
                'resume_stage': _text(getattr(recovery_plan, 'resume_stage', '')) or None,
                'anomaly_count': len(tuple(getattr(recovery_plan, 'anomalies', ()) or ())),
                'risk_flags': _risk_flags_tuple(getattr(recovery_plan, 'risk_flags', ()) or ()),
                'policy_snapshot': _mapping_copy(getattr(recovery_plan, 'policy_snapshot', {})),
            }
        return self.build({'tenant_id': required_tenant_id, 'run': run, 'controls': tuple(allowed_controls or ()), 'recent_events': tuple(recent_events or ()), 'recovery': recovery})


__all__ = ['CANON_WEB_RUN_CONTROL_PANEL', 'RunControlPanel']
