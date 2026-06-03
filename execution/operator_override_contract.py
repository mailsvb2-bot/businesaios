from __future__ import annotations

"""Canonical operator override contract.

Override remains subordinate to DecisionCore and the existing governance
approval flow. It models a one-shot human intervention bound to a single
execution subject fingerprint.
"""

import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol
from collections.abc import Mapping

from core.tenancy.normalization import require_tenant_id
from governance.rbac_contract import RoleId
from governance.role_catalog import RoleCatalog


CANON_OPERATOR_OVERRIDE_CONTRACT = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object, *, default: str = '') -> str:
    text = str(value or '').strip()
    return text or default


def _jsonable(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def build_operator_override_subject_fingerprint(
    *,
    tenant_id: str,
    execution_id: str,
    decision_id: str,
    action_name: str,
    subject_payload: Mapping[str, object] | None = None,
) -> str:
    canonical = {
        'tenant_id': require_tenant_id(tenant_id),
        'execution_id': _text(execution_id),
        'decision_id': _text(decision_id),
        'action_name': _text(action_name),
        'subject_payload': _jsonable(_safe_dict(subject_payload)),
    }
    if not canonical['execution_id']:
        raise ValueError('execution_id is required for subject fingerprint')
    if not canonical['decision_id']:
        raise ValueError('decision_id is required for subject fingerprint')
    if not canonical['action_name']:
        raise ValueError('action_name is required for subject fingerprint')
    raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


class OperatorOverrideStatus(str, Enum):
    REQUESTED = 'requested'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    CANCELLED = 'cancelled'
    EXPIRED = 'expired'
    CONSUMED = 'consumed'


class OperatorOverrideResolution(str, Enum):
    APPROVE_ONCE = 'approve_once'
    REJECT = 'reject'
    CANCEL = 'cancel'
    RETRY = 'retry'
    DOWNGRADE_TO_SUPERVISED = 'downgrade_to_supervised'


@dataclass(frozen=True)
class OperatorOverrideRequest:
    override_id: str
    tenant_id: str
    execution_id: str
    decision_id: str
    action_name: str
    requested_by: str
    reason: str
    subject_fingerprint: str
    requested_at: datetime = field(default_factory=utc_now)
    expires_at: datetime | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not _text(self.override_id):
            raise ValueError('override_id is required')
        require_tenant_id(self.tenant_id)
        if not _text(self.execution_id):
            raise ValueError('execution_id is required')
        if not _text(self.decision_id):
            raise ValueError('decision_id is required')
        if not _text(self.action_name):
            raise ValueError('action_name is required')
        if not _text(self.requested_by):
            raise ValueError('requested_by is required')
        if not _text(self.reason):
            raise ValueError('reason is required')
        if not _text(self.subject_fingerprint):
            raise ValueError('subject_fingerprint is required')
        if self.requested_at.tzinfo is None:
            raise ValueError('requested_at must be timezone-aware')
        if self.expires_at is not None:
            if self.expires_at.tzinfo is None:
                raise ValueError('expires_at must be timezone-aware')
            if self.expires_at <= self.requested_at:
                raise ValueError('expires_at must be greater than requested_at')

    @property
    def subject_type(self) -> str:
        return 'action_execution'

    @property
    def subject_id(self) -> str:
        return self.execution_id


@dataclass(frozen=True)
class OperatorOverrideDecision:
    override_id: str
    tenant_id: str
    actor_id: str
    role_id: RoleId
    resolution: OperatorOverrideResolution
    note: str
    decided_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not _text(self.override_id):
            raise ValueError('override_id is required')
        require_tenant_id(self.tenant_id)
        if not _text(self.actor_id):
            raise ValueError('actor_id is required')
        if not _text(self.note):
            raise ValueError('note is required')
        if self.decided_at.tzinfo is None:
            raise ValueError('decided_at must be timezone-aware')


@dataclass(frozen=True)
class OperatorOverrideRecord:
    request: OperatorOverrideRequest
    status: OperatorOverrideStatus
    decision: OperatorOverrideDecision | None = None
    final_reason: str | None = None
    consumed_at: datetime | None = None
    consumed_by_execution_id: str | None = None

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            OperatorOverrideStatus.APPROVED,
            OperatorOverrideStatus.REJECTED,
            OperatorOverrideStatus.CANCELLED,
            OperatorOverrideStatus.EXPIRED,
            OperatorOverrideStatus.CONSUMED,
        }

    @property
    def approved_once(self) -> bool:
        return bool(
            self.status is OperatorOverrideStatus.APPROVED
            and self.decision is not None
            and self.decision.resolution is OperatorOverrideResolution.APPROVE_ONCE
            and self.consumed_at is None
        )

    def validate_binding(
        self,
        *,
        tenant_id: str,
        execution_id: str,
        decision_id: str,
        action_name: str,
        subject_fingerprint: str,
    ) -> None:
        self.request.validate()
        if self.request.tenant_id != require_tenant_id(tenant_id):
            raise RuntimeError('cross_tenant_operator_override_forbidden')
        if self.request.execution_id != _text(execution_id):
            raise RuntimeError('operator_override_execution_id_mismatch')
        if self.request.decision_id != _text(decision_id):
            raise RuntimeError('operator_override_decision_id_mismatch')
        if self.request.action_name != _text(action_name):
            raise RuntimeError('operator_override_action_name_mismatch')
        if self.request.subject_fingerprint != _text(subject_fingerprint):
            raise RuntimeError('operator_override_subject_fingerprint_mismatch')
        if self.request.expires_at is not None and utc_now() > self.request.expires_at:
            raise RuntimeError('operator_override_expired')
        if self.status is OperatorOverrideStatus.CONSUMED:
            raise RuntimeError('operator_override_already_consumed')

    def consume_once(self, *, execution_id: str) -> 'OperatorOverrideRecord':
        if not self.approved_once:
            raise RuntimeError('operator_override_not_consumable')
        return replace(
            self,
            status=OperatorOverrideStatus.CONSUMED,
            consumed_at=utc_now(),
            consumed_by_execution_id=_text(execution_id),
            final_reason='approved_once_consumed',
        )


class OperatorOverrideStoreContract(Protocol):
    def create(self, request: OperatorOverrideRequest) -> OperatorOverrideRecord: ...
    def get(self, override_id: str) -> OperatorOverrideRecord | None: ...
    def save(self, record: OperatorOverrideRecord) -> OperatorOverrideRecord: ...
    def list_open(self, *, tenant_id: str) -> tuple[OperatorOverrideRecord, ...]: ...


def is_operator_override_role_allowed(role_id: RoleId) -> bool:
    catalog = RoleCatalog()
    if not catalog.is_human_approver_role(role_id):
        return False
    return role_id in {RoleId.OWNER, RoleId.OPERATOR, RoleId.SECURITY, RoleId.FINANCE}


def summarize_override_subject(
    *,
    tenant_id: str,
    execution_id: str,
    decision_id: str,
    action_name: str,
    metadata: Mapping[str, object] | None = None,
) -> dict[str, object]:
    meta = _safe_dict(metadata)
    return {
        'tenant_id': require_tenant_id(tenant_id),
        'execution_id': _text(execution_id),
        'decision_id': _text(decision_id),
        'action_name': _text(action_name),
        'impact_category': _text(meta.get('impact_category')),
        'external_confirmation_mode': _text(meta.get('external_confirmation_mode')),
        'requires_manual_review': bool(meta.get('requires_manual_review', False)),
        'tags': tuple(sorted(str(item).strip() for item in tuple(meta.get('tags', ()) or ()) if str(item).strip())),
    }


__all__ = [
    'CANON_OPERATOR_OVERRIDE_CONTRACT',
    'OperatorOverrideDecision',
    'OperatorOverrideRecord',
    'OperatorOverrideRequest',
    'OperatorOverrideResolution',
    'OperatorOverrideStatus',
    'OperatorOverrideStoreContract',
    'build_operator_override_subject_fingerprint',
    'is_operator_override_role_allowed',
    'summarize_override_subject',
    'utc_now',
]
