from __future__ import annotations

from datetime import datetime
from typing import Any

from core.tenancy.normalization import require_tenant_id
from runtime.queue.queue_alerts import QueueAlert

ROUTE_METADATA_MAX_ITEMS = 12
ROUTE_METADATA_MAX_STRING = 160
ROUTE_METADATA_REDACT_KEYS = ('token', 'secret', 'password', 'authorization', 'cookie', 'api_key', 'session', 'bearer')


def normalize_tenant_id(value: str) -> str:
    return require_tenant_id(value)


def normalize_queue_name(value: str) -> str:
    queue_name = str(value or '').strip()
    if not queue_name:
        raise ValueError('queue_name is required')
    return queue_name


def normalize_source(value: str | None) -> str:
    normalized = str(value or '').strip() or 'control_plane'
    return normalized.replace(' ', '_')


def normalize_hook_code(value: str) -> str:
    hook_code = str(value or '').strip()
    if not hook_code:
        raise ValueError('hook_code is required')
    return hook_code


def normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def alert_dict(alert: QueueAlert) -> dict[str, str]:
    return {
        'code': alert.code,
        'severity': alert.severity,
        'message': alert.message,
        'created_at': alert.created_at.isoformat(),
    }


def slo_dict(report: Any) -> dict[str, Any]:
    return {
        'tenant_id': str(report.tenant_id),
        'queue_name': str(report.queue_name),
        'ok': bool(report.ok),
        'status': str(report.status),
        'reasons': tuple(report.reasons),
        'pending_jobs': int(report.pending_jobs),
        'active_claims': int(report.active_claims),
        'dead_letter_jobs': int(report.dead_letter_jobs),
        'janitor_stale_seconds': report.janitor_stale_seconds,
        'leader_stale_seconds': report.leader_stale_seconds,
    }


def build_operator_summary(*, monitor_report: Any, analytics_preview: Any, audit_preview: dict[str, Any], approval_preview: dict[str, Any], trend_preview: dict[str, Any], data_freshness: dict[str, Any], consistency: dict[str, Any]) -> dict[str, Any]:
    alert_delivery = getattr(monitor_report, 'alert_delivery', None)
    backpressure = getattr(monitor_report, 'backpressure', None)
    return {
        'status': monitor_report.slo.status,
        'alert_count': len(tuple(monitor_report.alerts or ())),
        'critical_alert_count': sum(1 for item in tuple(monitor_report.alerts or ()) if str(getattr(item, 'severity', '')).strip() == 'critical'),
        'published_alert_count': 0 if alert_delivery is None else int(alert_delivery.published),
        'suppressed_alert_count': 0 if alert_delivery is None else int(alert_delivery.suppressed),
        'had_alert_suppression': False if alert_delivery is None else bool(alert_delivery.had_suppression),
        'backpressure_reason': None if backpressure is None else backpressure.global_verdict.reason,
        'starving_tenants': tuple(str(item) for item in tuple(() if backpressure is None else backpressure.global_verdict.starving_tenants or ())),
        'most_used_hook_code': analytics_preview.most_used_hook_code,
        'top_unexecuted_hook_code': analytics_preview.top_unexecuted_hook_code,
        'execution_rate': analytics_preview.execution_rate,
        'approval_required_count': int(approval_preview.get('approval_required_count', 0) or 0),
        'approval_required_hooks': tuple(approval_preview.get('approval_required_hooks', ()) or ()),
        'recent_route_action': audit_preview.get('latest_route_action'),
        'recent_route_status': audit_preview.get('latest_route_status'),
        'audit_execution_count': int(audit_preview.get('execution_count', 0) or 0),
        'audit_timeline_event_count': int(audit_preview.get('timeline_event_count', 0) or 0),
        'trend_direction': trend_preview.get('pending_direction'),
        'alert_churn': trend_preview.get('alert_churn'),
        'freshness_state': data_freshness.get('state'),
        'consistency_state': consistency.get('state'),
        'consistency_reasons': tuple(consistency.get('reasons', ()) or ()),
    }


def build_consistency_snapshot(*, monitor_report: Any, recent_alerts: Any, approval_preview: dict[str, Any], audit_preview: dict[str, Any], analytics_preview: Any, trend_preview: dict[str, Any], data_freshness: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    issues: list[str] = []
    state = 'ok'
    if approval_preview.get('approval_required_count', 0):
        reasons.append('operator_review_required')
        issues.append('operator_review_required')
    if str(data_freshness.get('state')) == 'stale':
        reasons.append('stale_data')
        issues.append('control_plane_data_stale')
    if int(audit_preview.get('timeline_event_count', 0) or 0) == 0:
        reasons.append('missing_audit_timeline')
        issues.append('missing_audit_timeline')
    if int(getattr(analytics_preview, 'execution_count', 0) or 0) > int(audit_preview.get('execution_count', 0) or 0):
        reasons.append('analytics_audit_mismatch')
        issues.append('analytics_audit_mismatch')
    if int(len(tuple(recent_alerts or ()))) > 0 and str(monitor_report.slo.status).strip() == 'ok':
        reasons.append('alerts_present_while_slo_ok')
        issues.append('alerts_present_while_slo_ok')
    if str(trend_preview.get('pending_direction')) == 'up' and str(monitor_report.slo.status).strip() == 'ok':
        reasons.append('pending_upward_pressure')
        issues.append('pending_upward_pressure')
    if reasons:
        state = 'degraded' if 'stale_data' in reasons or 'analytics_audit_mismatch' in reasons else 'warning'
    return {'state': state, 'reasons': tuple(reasons), 'issues': tuple(issues)}


def build_evidence_timeline(*, monitor_report: Any, recent_alerts: Any, remediation_plan: Any, approval_preview: dict[str, Any], route_timeline: tuple[dict[str, Any], ...], now: datetime, limit: int) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    sampled_at = getattr(monitor_report, 'sampled_at', None)
    if sampled_at is not None:
        rows.append({'entry_type': 'health_sample', 'kind': 'health_sample', 'at': sampled_at.isoformat(), 'title': f"Health sampled: {monitor_report.slo.status}", 'status': monitor_report.slo.status})
    for alert in tuple(recent_alerts or ()):
        rows.append({'entry_type': 'alert', 'kind': 'alert', 'at': alert.created_at.isoformat(), 'title': alert.code, 'status': alert.severity, 'message': alert.message})
    rows.append({'entry_type': 'remediation_plan', 'kind': 'remediation_plan', 'at': remediation_plan.generated_at.isoformat(), 'title': 'Remediation plan generated', 'status': 'planned', 'hook_count': len(tuple(remediation_plan.hooks or ()))})
    if int(approval_preview.get('approval_required_count', 0) or 0) > 0:
        rows.append({'entry_type': 'approval_gate', 'kind': 'approval_gate', 'at': now.isoformat(), 'title': 'Operator approval required', 'status': 'review_required', 'hook_count': int(approval_preview.get('approval_required_count', 0) or 0)})
    for item in route_timeline:
        row = dict(item)
        row.setdefault('entry_type', str(row.get('kind') or row.get('entry_type') or 'route_event'))
        rows.append(row)
    rows.sort(key=lambda item: (str(item.get('at') or ''), str(item.get('title') or '')), reverse=True)
    return tuple(rows[: max(1, int(limit))])


def build_timeline_rows(*, plans: Any, executions: Any, route_history: Any, limit: int) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for entry in tuple(plans or ()):
        rows.append({'entry_type': 'plan', 'at': entry.generated_at.isoformat(), 'title': 'Remediation plan generated', 'hook_count': len(tuple(entry.hooks or ())), 'status': 'planned'})
    for entry in tuple(executions or ()):
        rows.append({'entry_type': 'execution', 'at': entry.executed_at.isoformat(), 'title': str(entry.hook_code), 'status': 'executed' if bool(entry.executed) else 'review_required', 'reason': str(entry.reason), 'category': str(entry.category), 'metadata': sanitize_metadata(dict(getattr(entry, 'metadata', {}) or {}))})
    for entry in tuple(route_history or ()):
        rows.append({'entry_type': 'route_event', 'at': entry.recorded_at.isoformat(), 'title': str(entry.action), 'status': str(entry.status), 'source': str(entry.source), 'metadata': sanitize_metadata(dict(getattr(entry, 'metadata', {}) or {}))})
    rows.sort(key=lambda item: (str(item.get('at') or ''), str(item.get('title') or '')), reverse=True)
    return tuple(rows[: max(1, int(limit))])


def build_data_freshness(*, monitor_report: Any, rollup_summary: Any, now: datetime) -> dict[str, Any]:
    sampled_at = getattr(monitor_report, 'sampled_at', None) or now
    age_seconds = max(0, int((now - sampled_at).total_seconds()))
    rollup_last = None if rollup_summary is None else getattr(rollup_summary, 'last_observed_at', None)
    rollup_age = None if rollup_last is None else max(0, int((now - rollup_last).total_seconds()))
    state = 'fresh'
    reference_age = age_seconds if rollup_age is None else max(age_seconds, rollup_age)
    if reference_age >= 900:
        state = 'stale'
    elif reference_age >= 300:
        state = 'aging'
    return {'state': state, 'age_seconds': reference_age, 'sampled_at': sampled_at.isoformat(), 'last_rollup_at': None if rollup_last is None else rollup_last.isoformat()}


def sanitize_metadata(value: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    count = 0
    for key in sorted(value.keys(), key=lambda item: str(item)):
        if count >= ROUTE_METADATA_MAX_ITEMS:
            result['__truncated__'] = True
            break
        raw = value[key]
        name = str(key).strip() or '_'
        lowered = name.lower()
        if any(token in lowered for token in ROUTE_METADATA_REDACT_KEYS):
            result[name] = '[redacted]'
        else:
            result[name] = sanitize_value(raw)
        count += 1
    return result


def sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return sanitize_metadata(dict(value))
    if isinstance(value, (list, tuple)):
        items = [sanitize_value(item) for item in list(value)[:ROUTE_METADATA_MAX_ITEMS]]
        if len(value) > ROUTE_METADATA_MAX_ITEMS:
            items.append('[truncated]')
        return tuple(items)
    if isinstance(value, set):
        ordered = sorted(list(value), key=lambda item: repr(item))
        items = [sanitize_value(item) for item in ordered[:ROUTE_METADATA_MAX_ITEMS]]
        if len(ordered) > ROUTE_METADATA_MAX_ITEMS:
            items.append('[truncated]')
        return tuple(items)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        text = value.strip()
        return text if len(text) <= ROUTE_METADATA_MAX_STRING else text[:ROUTE_METADATA_MAX_STRING - 3] + '...'
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return repr(value)


def sanitize_hook_item(item: Any) -> Any:
    if isinstance(item, dict):
        normalized = dict(item)
        if 'metadata' in normalized:
            normalized['metadata'] = sanitize_metadata(dict(normalized.get('metadata') or {}))
        return normalized
    return item
