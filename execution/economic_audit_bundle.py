from __future__ import annotations

import json
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from execution.economic_bundle_quarantine import NoOpEconomicBundleQuarantine, build_quarantine_record
from execution.economic_export_manifest import build_economic_export_manifest, manifest_payload_for_digest, validate_economic_export_manifest
from execution.economic_retention_policy import EconomicRetentionPolicy, apply_economic_retention_policy
from execution.economic_schema_validation import EconomicSchemaValidator
from execution.economic_segment_validation import EconomicSegmentValidator
from execution.economic_semantic_validation import EconomicSemanticValidator
from execution.economic_scope_lineage import EconomicScopeLineageGuard
from execution.economic_lineage_lock import EconomicLineageLockBuilder
from execution.economic_bundle_immutability import EconomicBundleImmutabilityValidator
from execution.economic_schema_migration_matrix import EconomicSchemaMigrationMatrix
from observability.export_bundle_catalog import ExportBundleCatalog
from compliance.economic_forensics_service import EconomicForensicsService

CANON_ECONOMIC_AUDIT_BUNDLE = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or '').strip()


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _payload_for_immutability_digest(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    manifest = _safe_dict(normalized.get('export_manifest'))
    if manifest:
        manifest = dict(manifest)
        manifest.pop('immutable_payload_digest', None)
        normalized['export_manifest'] = manifest
    return normalized


def _scope_summary(scope: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _safe_dict(scope)
    return {
        'tenant_id': _text(payload.get('tenant_id')),
        'business_id': _text(payload.get('business_id')),
        'tenant_tier': _text(payload.get('tenant_tier')),
        'business_tier': _text(payload.get('business_tier')),
        'profile_name': _text(payload.get('profile_name')),
    }



def _collect_corruption_combinatorics_issues(
    *,
    manifest_validation: Mapping[str, Any],
    schema: object,
    semantic: object,
    scope_lineage: object,
    payload_digest_matches: bool,
    manifest_scope_summary: Mapping[str, Any],
    profile_scope_summary: Mapping[str, Any],
) -> list[str]:
    issues: list[str] = []
    manifest_valid = bool(manifest_validation.get('valid'))
    manifest_issues = {str(item) for item in manifest_validation.get('issues') or () if str(item)}
    schema_compatible = bool(getattr(schema, 'compatible', False))
    semantic_valid = bool(getattr(semantic, 'valid', False))
    migration_allowed = bool(getattr(scope_lineage, 'migration_allowed', False))
    scope_profile_mismatch = any(
        _text(manifest_scope_summary.get(key))
        and _text(profile_scope_summary.get(key))
        and _text(manifest_scope_summary.get(key)) != _text(profile_scope_summary.get(key))
        for key in ('tenant_id', 'business_id', 'tenant_tier', 'business_tier', 'profile_name')
    )

    if manifest_valid and not migration_allowed:
        issues.append('manifest_valid_lineage_invalid')
    if payload_digest_matches and not migration_allowed:
        issues.append('payload_valid_scope_lineage_invalid')
    if payload_digest_matches and scope_profile_mismatch:
        issues.append('payload_valid_scope_profile_invalid')
    if schema_compatible and not semantic_valid:
        issues.append('schema_valid_semantic_corruption')
    if 'scope_lineage_digest_mismatch' in manifest_issues and payload_digest_matches:
        issues.append('payload_valid_lineage_digest_conflict')
    return issues


def validate_economic_bundle_payload(
    *,
    bundle: Mapping[str, Any],
    expected_scope: Mapping[str, Any] | None = None,
    expected_profile_name: str | None = None,
    require_bundle_segment: bool = False,
) -> dict[str, Any]:
    normalized = _safe_dict(bundle)
    payload = _safe_dict(normalized.get('payload')) or normalized
    manifest = _safe_dict(payload.get('export_manifest'))
    metadata = _safe_dict(payload.get('metadata'))
    scope_profile = _safe_dict(metadata.get('scope_profile'))

    provided_digest = _text(normalized.get('digest'))
    expected_digest = sha256(_stable_json(payload).encode('utf-8')).hexdigest()
    payload_digest_matches = bool(provided_digest) and provided_digest == expected_digest

    manifest_validation = validate_economic_export_manifest(
        manifest=manifest,
        expected_scope=expected_scope,
        expected_profile_name=expected_profile_name,
        require_bundle=require_bundle_segment,
    ) if manifest else {
        'valid': False,
        'issues': ['export_manifest_missing'],
        'manifest_digest_matches': False,
        'expected_digest': '',
        'profile_name': '',
        'bundle_exists': False,
        'metadata': {'owner': 'execution.economic_audit_bundle'},
    }

    issues = list(manifest_validation.get('issues') or ())
    expected_scope_summary = _scope_summary(expected_scope)
    manifest_scope_summary = _scope_summary(manifest.get('scope'))
    profile_scope_summary = _scope_summary(scope_profile)
    for key in ('tenant_id', 'business_id', 'tenant_tier', 'business_tier', 'profile_name'):
        manifest_value = _text(manifest_scope_summary.get(key))
        profile_value = _text(profile_scope_summary.get(key))
        if manifest_value and profile_value and manifest_value != profile_value:
            issues.append(f'bundle_scope_profile_{key}_mismatch')
        expected_value = _text(expected_scope_summary.get(key))
        if expected_value and manifest_value and expected_value != manifest_value:
            issues.append(f'bundle_expected_scope_{key}_mismatch')

    if provided_digest and not payload_digest_matches:
        issues.append('bundle_digest_mismatch')

    schema = EconomicSchemaValidator().validate(payload=payload)
    migration = EconomicSchemaMigrationMatrix().validate(bundle_payload=payload)
    if not schema.compatible:
        issues.append(schema.reason)
    if not migration.supported:
        issues.append(migration.reason)

    segments = EconomicSegmentValidator().validate(payload=payload)
    if not segments.complete:
        issues.append(segments.reason)

    semantic = EconomicSemanticValidator().validate(payload=payload)
    if not semantic.valid:
        issues.append(semantic.reason)

    scope_lineage = EconomicScopeLineageGuard().validate(
        current_scope=expected_scope,
        incoming_scope=_safe_dict(manifest.get('scope')),
        declared_lineage=_safe_dict(manifest.get('scope_lineage')),
    )
    if not scope_lineage.migration_allowed:
        issues.append(scope_lineage.reason)

    lineage_lock = EconomicLineageLockBuilder().validate(
        manifest=manifest,
        expected_scope=expected_scope,
    )
    if not lineage_lock.valid:
        issues.append(lineage_lock.reason)

    immutability = EconomicBundleImmutabilityValidator().validate(bundle=normalized)
    if not immutability.valid:
        issues.append(immutability.reason)

    issues.extend(_collect_corruption_combinatorics_issues(
        manifest_validation=manifest_validation,
        schema=schema,
        semantic=semantic,
        scope_lineage=scope_lineage,
        payload_digest_matches=payload_digest_matches,
        manifest_scope_summary=manifest_scope_summary,
        profile_scope_summary=profile_scope_summary,
    ))

    valid = not issues
    return {
        'valid': valid,
        'issues': list(dict.fromkeys(issues)),
        'manifest_validation': manifest_validation,
        'payload_digest_matches': payload_digest_matches,
        'expected_payload_digest': expected_digest,
        'scope_summary': manifest_scope_summary,
        'scope_profile_summary': profile_scope_summary,
        'schema': schema.to_dict(),
        'migration': migration.to_dict(),
        'segments': segments.to_dict(),
        'semantic': semantic.to_dict(),
        'scope_lineage': scope_lineage.to_dict(),
        'lineage_lock': lineage_lock.to_dict(),
        'immutability': immutability.to_dict(),
        'metadata': {
            'owner': 'execution.economic_audit_bundle',
        },
    }


@dataclass(frozen=True, slots=True)
class EconomicAuditBundle:
    bundle_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    digest: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {'bundle_id': self.bundle_id, 'digest': self.digest, 'payload': dict(self.payload)}


class EconomicAuditBundleService:
    """
    Export/import helper for canonical economic audit artifacts.

    Important:
    - Does not compute new policy.
    - Does not decide.
    - Only packages existing canonical store outputs for audit/export/recovery handoff.
    """

    def __init__(self, *, quarantine_sink: object | None = None, forensics_service: EconomicForensicsService | None = None) -> None:
        self._quarantine_sink = quarantine_sink or NoOpEconomicBundleQuarantine()
        self._forensics_service = forensics_service or EconomicForensicsService()

    def build_bundle(
        self,
        *,
        bundle_id: str,
        feedback_rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
        roi_rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
        snapshot_rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
        trace_rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
        metrics_rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
        audit_summary: Mapping[str, Any] | None = None,
        export_manifest: Mapping[str, Any] | None = None,
        retention_policy: EconomicRetentionPolicy | Mapping[str, Any] | None = None,
        scope_profile: Mapping[str, Any] | None = None,
    ) -> EconomicAuditBundle:
        payload = {
            'bundle_id': _text(bundle_id) or 'economic-audit-bundle',
            'feedback_rows': [dict(row) for row in feedback_rows],
            'roi_rows': [dict(row) for row in roi_rows],
            'snapshot_rows': [dict(row) for row in snapshot_rows],
            'trace_rows': [dict(row) for row in trace_rows],
            'metrics_rows': [dict(row) for row in metrics_rows],
            'audit_summary': dict(audit_summary or {}),
            'export_manifest': dict(export_manifest or {}),
            'metadata': {
                'owner': 'execution.economic_audit_bundle',
                'scope_profile': dict(scope_profile or {}),
                'counts': {
                    'feedback': len(tuple(feedback_rows)),
                    'roi': len(tuple(roi_rows)),
                    'snapshots': len(tuple(snapshot_rows)),
                    'traces': len(tuple(trace_rows)),
                    'metrics': len(tuple(metrics_rows)),
                },
            },
        }
        if retention_policy is not None:
            policy = retention_policy if isinstance(retention_policy, EconomicRetentionPolicy) else EconomicRetentionPolicy.from_mapping(retention_policy)
            applied = apply_economic_retention_policy(payload=payload, retention_policy=policy)
            payload = applied.payload
            payload['export_manifest'] = {
                **dict(export_manifest or {}),
                'retention': dict(applied.retention),
            }
        manifest = _safe_dict(payload.get('export_manifest'))
        if manifest:
            manifest['immutable_payload_digest'] = ''
            manifest['manifest_digest'] = sha256(
                _stable_json(manifest_payload_for_digest(manifest)).encode('utf-8')
            ).hexdigest()
            payload['export_manifest'] = manifest
            immutable_payload_digest = sha256(_stable_json(_payload_for_immutability_digest(payload)).encode('utf-8')).hexdigest()
            manifest['immutable_payload_digest'] = immutable_payload_digest
            payload['export_manifest'] = manifest
        digest = sha256(_stable_json(payload).encode('utf-8')).hexdigest()
        return EconomicAuditBundle(bundle_id=payload['bundle_id'], payload=payload, digest=digest)

    def export_json(self, *, bundle: EconomicAuditBundle, path: str | Path) -> str:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_stable_json(bundle.to_dict()), encoding='utf-8')
        manifest = _safe_dict(bundle.payload.get('export_manifest'))
        self._forensics_service.record_event(
            event_type='economic_bundle_exported',
            severity='info',
            artifact_id=bundle.bundle_id,
            artifact_digest=bundle.digest,
            scope=_safe_dict(manifest.get('scope')),
            schema_version=_text(manifest.get('bundle_schema_version')),
            payload={'path': str(target), 'manifest_digest': _text(manifest.get('manifest_digest'))},
            tags=('economic', 'export', 'forensics'),
        )
        return str(target)

    def import_json(
        self,
        *,
        path: str | Path,
        strict_validation: bool = False,
        expected_scope: Mapping[str, Any] | None = None,
        expected_profile_name: str | None = None,
        require_bundle_segment: bool = False,
    ) -> EconomicAuditBundle:
        target = Path(path)
        try:
            data = json.loads(target.read_text(encoding='utf-8'))
        except Exception as exc:
            self._quarantine_sink.record(build_quarantine_record(
                bundle_path=target,
                reason='economic_bundle_parse_failed',
                issues=[str(exc)],
                scope=expected_scope,
                metadata={'profile_name': _text(expected_profile_name)},
            ))
            raise
        payload = _safe_dict(data.get('payload'))
        digest = _text(data.get('digest')) or sha256(_stable_json(payload).encode('utf-8')).hexdigest()
        bundle = EconomicAuditBundle(bundle_id=_text(data.get('bundle_id') or payload.get('bundle_id')), payload=payload, digest=digest)
        quarantine_denied = getattr(self._quarantine_sink, 'is_digest_denied', None)
        if callable(quarantine_denied) and quarantine_denied(digest):
            raise ValueError('economic bundle import denied by poisoned digest')
        if strict_validation:
            validation = validate_economic_bundle_payload(
                bundle=bundle.to_dict(),
                expected_scope=expected_scope,
                expected_profile_name=expected_profile_name,
                require_bundle_segment=require_bundle_segment,
            )
            if not validation['valid']:
                poisoned = 'manifest_digest_mismatch' in validation['issues'] or 'bundle_digest_mismatch' in validation['issues']
                self._quarantine_sink.record(build_quarantine_record(
                    bundle_path=target,
                    reason='economic_bundle_validation_failed',
                    issues=list(validation['issues']),
                    scope=validation.get('scope_summary') or expected_scope,
                    metadata={'profile_name': _text(expected_profile_name), 'validation_source': 'import_json', 'artifact_digest': digest, 'poisoned': poisoned},
                ))
                self._forensics_service.record_event(
                    event_type='economic_bundle_validation_failed',
                    severity='critical',
                    artifact_id=bundle.bundle_id,
                    artifact_digest=digest,
                    scope=validation.get('scope_summary') or expected_scope,
                    schema_version=_text(_safe_dict(payload.get('export_manifest')).get('bundle_schema_version')),
                    payload={'issues': list(validation['issues'])[:20]},
                    tags=('economic', 'import', 'forensics', 'validation_failed'),
                )
                if poisoned and hasattr(self._quarantine_sink, 'transition_status'):
                    self._quarantine_sink.transition_status(artifact_digest=digest, status='denied', poisoned=True)
                raise ValueError('economic bundle validation failed: ' + ','.join(validation['issues']))
            self._forensics_service.record_event(
                event_type='economic_bundle_import_validated',
                severity='info',
                artifact_id=bundle.bundle_id,
                artifact_digest=digest,
                scope=validation.get('scope_summary') or expected_scope,
                schema_version=_text(_safe_dict(payload.get('export_manifest')).get('bundle_schema_version')),
                payload={'migration': _safe_dict(validation.get('migration')), 'issues': []},
                tags=('economic', 'import', 'forensics', 'validated'),
            )
        return bundle

    def build_export_manifest(
        self,
        *,
        stores: Mapping[str, object],
        bundle_path: str | Path | None = None,
        retention: Mapping[str, Any] | None = None,
        node_id: str | None = None,
        scope: Mapping[str, Any] | None = None,
        scope_lineage: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return build_economic_export_manifest(
            stores=dict(stores),
            bundle_path=bundle_path,
            retention=retention,
            node_id=node_id,
            scope=scope,
            scope_lineage=scope_lineage,
        )

    def write_bundle(
        self,
        *,
        bundle: EconomicAuditBundle,
        root_dir: str | Path,
        bundle_name: str | None = None,
        catalog_path: str | Path | None = None,
    ) -> dict[str, Any]:
        root = Path(root_dir)
        bundles_dir = root / 'economic' / 'bundles'
        bundles_dir.mkdir(parents=True, exist_ok=True)
        normalized_name = _text(bundle_name) or _text(bundle.bundle_id) or 'economic-audit-bundle'
        path = bundles_dir / f'{normalized_name}.json'
        self.export_json(bundle=bundle, path=path)

        entry_payload = {
            'bundle_kind': 'economic',
            'bundle_name': normalized_name,
            'path': str(path),
        }
        if catalog_path is not None:
            catalog = ExportBundleCatalog(catalog_path)
            entry = catalog.register(bundle_kind='economic', bundle_name=normalized_name, path=path, payload=bundle.to_dict())
            entry_payload.update({
                'generated_at': entry.generated_at,
                'payload_sha256': entry.payload_sha256,
                'catalog_path': str(catalog.path),
            })
        return entry_payload

    def restore_bundle(
        self,
        *,
        bundle_path: str | Path,
        strict_validation: bool = False,
        expected_scope: Mapping[str, Any] | None = None,
        expected_profile_name: str | None = None,
        require_bundle_segment: bool = False,
    ) -> dict[str, Any]:
        return self.import_json(
            path=bundle_path,
            strict_validation=strict_validation,
            expected_scope=expected_scope,
            expected_profile_name=expected_profile_name,
            require_bundle_segment=require_bundle_segment,
        ).to_dict()


__all__ = [
    'CANON_ECONOMIC_AUDIT_BUNDLE',
    'EconomicAuditBundle',
    'EconomicAuditBundleService',
    'validate_economic_bundle_payload',
]
