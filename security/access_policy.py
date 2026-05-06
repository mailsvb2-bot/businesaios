from __future__ import annotations

"""Canonical security access policy.

This module gates access to sensitive resources. It does not choose business
strategy and must never become a second decision path.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from compliance.data_classification import (
    DataCategory,
    DataClassificationResult,
    DataSensitivity,
    KeywordDataClassifier,
)
from governance.permission_matrix import PermissionMatrix
from governance.rbac_contract import AccessRequest, ActorContext, Permission, ResourceRef
from governance.rbac_policy import RbacPolicy
from governance.role_catalog import RoleCatalog


CANON_SECURITY_ACCESS_POLICY = True


class SecurityAction(str, Enum):
    READ = 'read'
    WRITE = 'write'
    EXPORT = 'export'
    ADMIN = 'admin'


@dataclass(frozen=True)
class SecurityResource:
    resource_type: str
    resource_id: str
    tenant_id: str
    classification: DataClassificationResult
    encryption_required: bool = False
    attributes: Mapping[str, object] = field(default_factory=dict)

    def to_resource_ref(self) -> ResourceRef:
        return ResourceRef(
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            tenant_id=self.tenant_id,
            attributes={
                **dict(self.attributes),
                'classification': self.classification.category.value,
                'sensitivity': self.classification.sensitivity.value,
                'encryption_required': self.encryption_required,
            },
        )


@dataclass(frozen=True)
class AccessPolicyVerdict:
    allowed: bool
    reason: str
    operator_required: bool = False
    required_permission: Permission | None = None
    classification: str | None = None
    sensitivity: str | None = None
    labels: Mapping[str, str] = field(default_factory=dict)


@dataclass
class DataAccessPolicy:
    rbac_policy: RbacPolicy = field(
        default_factory=lambda: RbacPolicy(
            role_catalog=RoleCatalog(),
            permission_matrix=PermissionMatrix(),
        )
    )
    classifier: KeywordDataClassifier = field(default_factory=KeywordDataClassifier)

    def classify_payload(
        self,
        *,
        asset_id: str,
        name: str,
        content_type: str,
        tags: tuple[str, ...] = (),
        metadata: Mapping[str, object] | None = None,
        source_system: str | None = None,
        region_hint: str | None = None,
    ) -> DataClassificationResult:
        from compliance.data_classification import DataAsset

        asset = DataAsset(
            asset_id=asset_id,
            name=name,
            content_type=content_type,
            tags=tuple(tags),
            metadata=dict(metadata or {}),
            source_system=source_system,
            region_hint=region_hint,
        )
        return self.classifier.classify(asset)

    def evaluate(
        self,
        *,
        actor: ActorContext,
        action: SecurityAction,
        resource: SecurityResource,
        transport_encrypted: bool,
        metadata: Mapping[str, object] | None = None,
    ) -> AccessPolicyVerdict:
        actor.validate()
        request = AccessRequest(
            actor=actor,
            permission=self._required_permission(action=action, classification=resource.classification),
            resource=resource.to_resource_ref(),
            action_name=f'{resource.resource_type}:{action.value}',
            metadata={
                **dict(metadata or {}),
                'action_category': self._action_category(action=action),
                'classification': resource.classification.category.value,
                'sensitivity': resource.classification.sensitivity.value,
            },
        )
        rbac_verdict = self.rbac_policy.evaluate(request)
        if not rbac_verdict.allowed:
            return AccessPolicyVerdict(
                allowed=False,
                reason=rbac_verdict.reason,
                operator_required=rbac_verdict.operator_required,
                required_permission=request.permission,
                classification=resource.classification.category.value,
                sensitivity=resource.classification.sensitivity.value,
                labels={k: str(v) for k, v in rbac_verdict.audit_fields.items()},
            )
        if resource.encryption_required and not transport_encrypted:
            return AccessPolicyVerdict(
                allowed=False,
                reason='encryption_required',
                operator_required=True,
                required_permission=request.permission,
                classification=resource.classification.category.value,
                sensitivity=resource.classification.sensitivity.value,
                labels={'transport_encrypted': 'false'},
            )
        if action is SecurityAction.EXPORT and resource.classification.sensitivity in {DataSensitivity.HIGH, DataSensitivity.CRITICAL}:
            return AccessPolicyVerdict(
                allowed=False,
                reason='high_sensitivity_export_requires_operator',
                operator_required=True,
                required_permission=request.permission,
                classification=resource.classification.category.value,
                sensitivity=resource.classification.sensitivity.value,
                labels={'regulated_markers': ','.join(resource.classification.regulated_markers)},
            )
        return AccessPolicyVerdict(
            allowed=True,
            reason='allowed',
            operator_required=False,
            required_permission=request.permission,
            classification=resource.classification.category.value,
            sensitivity=resource.classification.sensitivity.value,
            labels={
                'classification_confidence': f'{resource.classification.classification_confidence:.2f}',
                'transport_encrypted': 'true' if transport_encrypted else 'false',
            },
        )

    @staticmethod
    def _required_permission(*, action: SecurityAction, classification: DataClassificationResult) -> Permission:
        if action is SecurityAction.READ:
            return Permission.VIEW_AUDIT if classification.category in {DataCategory.RESTRICTED, DataCategory.REGULATED} else Permission.VIEW_POLICY
        if action is SecurityAction.WRITE:
            return Permission.EXECUTE_INTERNAL_WRITE
        if action is SecurityAction.EXPORT:
            return Permission.VIEW_AUDIT
        return Permission.MANAGE_TENANT_POLICY

    @staticmethod
    def _action_category(*, action: SecurityAction) -> str:
        if action is SecurityAction.READ:
            return 'safe_read'
        if action is SecurityAction.WRITE:
            return 'internal_write'
        if action is SecurityAction.EXPORT:
            return 'outbound'
        return 'strategic_change'


__all__ = [
    'AccessPolicyVerdict',
    'CANON_SECURITY_ACCESS_POLICY',
    'DataAccessPolicy',
    'SecurityAction',
    'SecurityResource',
]
