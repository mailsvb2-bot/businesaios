from __future__ import annotations

from typing import Any, Mapping

from application.decision.action_result import ActionExecutionResult
from application.capability.capability_operator_view import normalize_capability_view
from entrypoints.api.action_models import ExecuteActionResponse


CANON_API_EXECUTE_ACTION_RESPONSE_PRESENTER = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str | None:
    text = str(value or '').strip()
    return text or None


def _result_mapping(result: ActionExecutionResult | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(result, ActionExecutionResult):
        return {
            'status': result.status,
            'action_type': result.action_type,
            'reason': result.reason,
            'details': dict(result.details),
        }
    return dict(result)


def _normalized_details(raw: Mapping[str, Any]) -> dict[str, Any]:
    details = _safe_dict(raw.get('details'))
    if details:
        return details

    details = dict(raw)
    details.pop('status', None)
    details.pop('action_type', None)
    details.pop('reason', None)
    details.pop('capability_view', None)
    return details


def _normalized_capability_view(raw: Mapping[str, Any], details: Mapping[str, Any]) -> dict[str, Any]:
    explicit_view = raw.get('capability_view')
    if isinstance(explicit_view, Mapping):
        return normalize_capability_view(explicit_view)
    return normalize_capability_view(details)


def present_execute_action_response(
    result: ActionExecutionResult | Mapping[str, Any],
) -> ExecuteActionResponse:
    raw = _result_mapping(result)
    details = _normalized_details(raw)
    capability_view = _normalized_capability_view(raw, details)

    return ExecuteActionResponse(
        status=str(raw.get('status') or ''),
        action_type=str(raw.get('action_type') or ''),
        reason=_text(raw.get('reason')),
        details=details,
        capability_view=capability_view,
    )


def present_blocked_execute_action_response(
    *,
    action_type: str,
    reason: object,
    details: Mapping[str, Any] | None = None,
    capability_view: Mapping[str, Any] | None = None,
) -> ExecuteActionResponse:
    payload: dict[str, Any] = {
        'status': 'blocked',
        'action_type': str(action_type or ''),
        'reason': _text(reason),
        'details': dict(details or {}),
    }
    if isinstance(capability_view, Mapping):
        payload['capability_view'] = dict(capability_view)
    return present_execute_action_response(payload)


__all__ = [
    'CANON_API_EXECUTE_ACTION_RESPONSE_PRESENTER',
    'present_execute_action_response',
    'present_blocked_execute_action_response',
]
