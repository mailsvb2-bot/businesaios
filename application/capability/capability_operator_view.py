from __future__ import annotations

from typing import Any, Mapping

CANON_CAPABILITY_OPERATOR_VIEW = True


_SURFACE_KEYS = ('diagnostics', 'execution_verdict', 'policy_verdict')
_CAPABILITY_FLAG_KEYS = ('allowed', 'fallback_used', 'reason')


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or '').strip()


def _first_text(*values: object) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ''


def _merge_signal_collections(*values: object) -> tuple[Any, ...]:
    merged: list[Any] = []
    for value in values:
        if not isinstance(value, (list, tuple)):
            continue
        for item in value:
            if item not in merged:
                merged.append(item)
    return tuple(merged)


def _merge_dict_payload(base: Mapping[str, Any] | None, extra: Mapping[str, Any] | None) -> dict[str, Any]:
    left = _safe_dict(base)
    right = _safe_dict(extra)
    if not left:
        return right
    if not right:
        return left
    merged = dict(left)
    for key, value in right.items():
        if key == 'signals':
            merged[key] = list(_merge_signal_collections(left.get(key), value))
            continue
        if key not in merged or merged[key] in (None, '', (), [], {}):
            merged[key] = value
            continue
        if isinstance(merged[key], Mapping) and isinstance(value, Mapping):
            merged[key] = _merge_dict_payload(_safe_dict(merged[key]), _safe_dict(value))
            continue
        if isinstance(merged[key], (list, tuple)) and isinstance(value, (list, tuple)):
            merged[key] = list(_merge_signal_collections(merged[key], value))
            continue
        merged[key] = value
    return merged


def merge_capability_views(*values: Mapping[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    capability: dict[str, Any] = {}
    for raw in values:
        normalized = normalize_capability_view(raw)
        if not normalized:
            continue
        tenant_id = _text(normalized.get('tenant_id'))
        if tenant_id and 'tenant_id' not in merged:
            merged['tenant_id'] = tenant_id
        for key in _SURFACE_KEYS:
            payload = _safe_dict(normalized.get(key))
            if payload:
                merged[key] = _merge_dict_payload(merged.get(key), payload)
        nested_capability = _safe_dict(normalized.get('capability'))
        if nested_capability:
            capability = _merge_dict_payload(capability, nested_capability)
    if capability:
        merged['capability'] = capability
    return merged


def normalize_capability_view(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """
    Canonical read-only normalization for operator-facing capability state.

    Accepts any of these shapes:
    - full capability view: {diagnostics, execution_verdict, policy_verdict, ...}
    - action/result payload patch: {capability_diagnostics, execution_verdict, policy_verdict, ...}
    - compatibility planner output: {capability: {...}, allowed, fallback_used, reason, ...}
    - final feedback payload: {capability_planning: {...}, capability_diagnostics, ...}
    - result/output shape: {output: {...}} or {feedback: {...}}
    """
    root = _safe_dict(value)
    if not root:
        return {}

    nested_view = merge_capability_views(
        _safe_dict(root.get('capability_view')),
        _safe_dict(root.get('output')),
        _safe_dict(root.get('feedback')),
    )

    planning = _safe_dict(root.get('capability_planning'))
    nested_capability = _merge_dict_payload(
        _safe_dict(root.get('capability') or planning.get('capability')),
        _safe_dict(nested_view.get('capability')),
    )

    diagnostics = _merge_dict_payload(
        _merge_dict_payload(
            _safe_dict(root.get('diagnostics')),
            _safe_dict(root.get('capability_diagnostics')),
        ),
        _merge_dict_payload(
            _safe_dict(nested_capability.get('diagnostics')),
            _safe_dict(nested_view.get('diagnostics')),
        ),
    )
    execution_verdict = _merge_dict_payload(
        _merge_dict_payload(
            _safe_dict(root.get('execution_verdict')),
            _safe_dict(nested_capability.get('execution_verdict')),
        ),
        _safe_dict(nested_view.get('execution_verdict')),
    )
    policy_verdict = _merge_dict_payload(
        _merge_dict_payload(
            _safe_dict(root.get('policy_verdict')),
            _safe_dict(nested_capability.get('policy_verdict')),
        ),
        _safe_dict(nested_view.get('policy_verdict')),
    )

    capability: dict[str, Any] = dict(nested_capability)
    for key in _CAPABILITY_FLAG_KEYS:
        source_value = root.get(key)
        if source_value is None:
            source_value = planning.get(key)
        if source_value is not None and key not in capability:
            capability[key] = source_value

    if diagnostics:
        capability.setdefault('diagnostics', diagnostics)
    if execution_verdict:
        capability.setdefault('execution_verdict', execution_verdict)
    if policy_verdict:
        capability.setdefault('policy_verdict', policy_verdict)

    if not diagnostics and not execution_verdict and not policy_verdict and not capability:
        return {}

    normalized: dict[str, Any] = {}
    tenant_id = _first_text(root.get('tenant_id'), nested_capability.get('tenant_id'), planning.get('tenant_id'), nested_view.get('tenant_id'))
    if tenant_id:
        normalized['tenant_id'] = tenant_id
    if diagnostics:
        normalized['diagnostics'] = diagnostics
    if execution_verdict:
        normalized['execution_verdict'] = execution_verdict
    if policy_verdict:
        normalized['policy_verdict'] = policy_verdict
    if capability:
        normalized['capability'] = capability
    return normalized


__all__ = ['CANON_CAPABILITY_OPERATOR_VIEW', 'merge_capability_views', 'normalize_capability_view']
