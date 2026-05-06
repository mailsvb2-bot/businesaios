from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json

from execution.economic_policy_fingerprint import EconomicPolicyFingerprintBuilder
from execution.economic_schema_migration_matrix import CURRENT_ECONOMIC_BUNDLE_SCHEMA_VERSION
from execution.economic_lineage_lock import EconomicLineageLockBuilder

CANON_ECONOMIC_EXPORT_MANIFEST = True


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _segment_payload(path: Path) -> dict[str, Any]:
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    return {
        'path': str(path),
        'filename': path.name,
        'bytes': int(size),
        'exists': path.exists(),
    }


def _store_path(store: object) -> Path | None:
    path = getattr(store, 'path', None)
    if path is None:
        path = getattr(store, '_path', None)
    if path is None:
        return None
    return Path(path)


def _row_count(store: object) -> int | None:
    list_rows = getattr(store, 'list_rows', None)
    if list_rows is None:
        return None
    try:
        rows = list_rows()
    except Exception:
        return None
    try:
        return len(tuple(rows))
    except Exception:
        return None


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or '').strip()


def _stable_digest(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return sha256(raw).hexdigest()


def build_scope_lineage_digest(*, scope: Mapping[str, Any] | None, scope_lineage: Mapping[str, Any] | None) -> str:
    lineage_payload = {
        'scope': dict(scope or {}),
        'scope_lineage': dict(scope_lineage or {}),
    }
    return _stable_digest(lineage_payload)


def manifest_payload_for_digest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(manifest)
    payload.pop('manifest_digest', None)
    payload.pop('immutable_payload_digest', None)
    return payload


def manifest_profile_name(manifest: Mapping[str, Any] | None) -> str:
    scope = _safe_dict(_safe_dict(manifest).get('scope'))
    return _text(scope.get('profile_name'))


def validate_economic_export_manifest(
    *,
    manifest: Mapping[str, Any],
    expected_scope: Mapping[str, Any] | None = None,
    expected_profile_name: str | None = None,
    expected_node_id: str | None = None,
    require_bundle: bool = False,
) -> dict[str, Any]:
    normalized = _safe_dict(manifest)
    issues: list[str] = []
    expected_digest = _stable_digest(manifest_payload_for_digest(normalized))
    provided_digest = _text(normalized.get('manifest_digest'))
    digest_matches = bool(provided_digest) and provided_digest == expected_digest
    if not digest_matches:
        issues.append('manifest_digest_mismatch')

    scope = _safe_dict(normalized.get('scope'))
    if expected_scope is not None:
        expected_scope_dict = _safe_dict(expected_scope)
        for key in ('tenant_id', 'business_id', 'tenant_tier', 'business_tier', 'profile_name'):
            expected_value = _text(expected_scope_dict.get(key))
            actual_value = _text(scope.get(key))
            if expected_value and actual_value and expected_value != actual_value:
                issues.append(f'scope_{key}_mismatch')

    profile_name = _text(expected_profile_name) or manifest_profile_name(normalized)
    if _text(expected_profile_name) and profile_name != _text(expected_profile_name):
        issues.append('profile_name_mismatch')

    if expected_node_id is not None:
        actual_node_id = _text(normalized.get('node_id'))
        if actual_node_id and actual_node_id != _text(expected_node_id):
            issues.append('node_id_mismatch')

    bundle_payload = _safe_dict(normalized.get('bundle'))
    if require_bundle and not bundle_payload:
        issues.append('bundle_segment_missing')

    bundle_exists = True
    bundle_path = _text(bundle_payload.get('path'))
    if bundle_path:
        bundle_exists = Path(bundle_path).exists()
        if not bundle_exists:
            issues.append('bundle_path_missing')

    policy_fingerprint = _safe_dict(normalized.get('policy_fingerprint'))
    expected_policy_fingerprint = EconomicPolicyFingerprintBuilder().build(scope_profile=scope).fingerprint if scope else ''
    if policy_fingerprint and expected_policy_fingerprint:
        actual_fingerprint = _text(policy_fingerprint.get('fingerprint'))
        if actual_fingerprint and actual_fingerprint != expected_policy_fingerprint:
            issues.append('policy_fingerprint_mismatch')

    schema_version = _text(normalized.get('bundle_schema_version') or '1')
    if schema_version != '2':
        issues.append('bundle_schema_version_incompatible')

    provided_scope_lineage_digest = _text(normalized.get('scope_lineage_digest'))
    expected_scope_lineage_digest = build_scope_lineage_digest(scope=scope, scope_lineage=_safe_dict(normalized.get('scope_lineage')))
    if provided_scope_lineage_digest and provided_scope_lineage_digest != expected_scope_lineage_digest:
        issues.append('scope_lineage_digest_mismatch')

    return {
        'valid': not issues,
        'issues': list(dict.fromkeys(issues)),
        'manifest_digest_matches': digest_matches,
        'expected_digest': expected_digest,
        'profile_name': profile_name,
        'bundle_exists': bundle_exists,
        'metadata': {
            'owner': 'execution.economic_export_manifest',
            'scope_lineage_present': bool(_safe_dict(normalized.get('scope_lineage'))),
        },
    }


def build_economic_export_manifest(
    *,
    stores: dict[str, object],
    bundle_path: str | Path | None = None,
    retention: Mapping[str, Any] | None = None,
    node_id: str | None = None,
    scope: Mapping[str, Any] | None = None,
    scope_lineage: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    scope_payload = dict(scope or {})
    lineage_lock = {
        'lineage_hash': EconomicLineageLockBuilder().build_hash(scope=scope_payload, scope_lineage=scope_lineage),
        'parents': list(_safe_dict(scope_lineage).get('parents') or ()),
    }
    payload: dict[str, Any] = {
        'manifest_version': 2,
        'bundle_schema_version': CURRENT_ECONOMIC_BUNDLE_SCHEMA_VERSION,
        'generated_at': _utc_now(),
        'node_id': str(node_id or 'local-primary'),
        'scope': scope_payload,
        'scope_lineage': dict(scope_lineage or {}),
        'lineage_lock': lineage_lock,
        'policy_fingerprint': EconomicPolicyFingerprintBuilder().build(scope_profile=scope_payload).to_dict(),
        'scope_lineage_digest': build_scope_lineage_digest(scope=scope_payload, scope_lineage=scope_lineage),
        'immutable_bundle': True,
        'migration_matrix': {
            'current_version': CURRENT_ECONOMIC_BUNDLE_SCHEMA_VERSION,
            'supported_upgrade_from': ['1', CURRENT_ECONOMIC_BUNDLE_SCHEMA_VERSION],
            'downgrade_allowed': False,
        },
    }
    for name, store in stores.items():
        path = _store_path(store)
        row_count = _row_count(store)
        if path is None:
            payload[name] = {
                'backend': type(store).__name__,
                'path': None,
                'exists': False,
                'bytes': 0,
                'row_count': row_count,
            }
            continue
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        payload[name] = {
            'backend': type(store).__name__,
            'path': str(path),
            'exists': path.exists(),
            'bytes': int(size),
            'row_count': row_count,
        }
    if bundle_path is not None:
        payload['bundle'] = _segment_payload(Path(bundle_path))
    if retention is not None:
        payload['retention'] = {'policy': dict(retention)}
    payload['manifest_digest'] = _stable_digest(payload)
    payload['immutable_payload_digest'] = ''
    return payload


__all__ = [
    'CANON_ECONOMIC_EXPORT_MANIFEST',
    'build_economic_export_manifest',
    'build_scope_lineage_digest',
    'manifest_payload_for_digest',
    'manifest_profile_name',
    'validate_economic_export_manifest',
]
