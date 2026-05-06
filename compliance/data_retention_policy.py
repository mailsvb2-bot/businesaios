from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Mapping, Optional

from compliance.base import ComplianceValidationError, PolicyMetadata


class RetentionPolicyLevel(str, Enum):
    SHORT = 'short'
    STANDARD = 'standard'
    LONG = 'long'
    REGULATED = 'regulated'
    IMMUTABLE_AUDIT = 'immutable_audit'


@dataclass(frozen=True)
class DataRetentionRule:
    profile: str
    level: RetentionPolicyLevel
    retention_days: int
    legal_hold_supported: bool = True
    hard_delete_required: bool = False
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class RetentionDecision:
    profile: str
    level: RetentionPolicyLevel
    created_at: datetime
    retain_until: datetime
    legal_hold_applied: bool
    hard_delete_required: bool
    reasons: tuple[str, ...]
    policy: PolicyMetadata


class DataRetentionPolicy:
    def __init__(
        self,
        rules: Optional[Mapping[str, DataRetentionRule]] = None,
        *,
        policy_version: str = '2.0',
    ) -> None:
        self._policy = PolicyMetadata(
            policy_name='data_retention_policy',
            policy_version=policy_version,
            tags=('retention', 'compliance'),
        )
        base_rules = {
            'public_default': DataRetentionRule('public_default', RetentionPolicyLevel.SHORT, 30),
            'internal_default': DataRetentionRule('internal_default', RetentionPolicyLevel.STANDARD, 180),
            'personal_data': DataRetentionRule(
                'personal_data',
                RetentionPolicyLevel.LONG,
                365,
                hard_delete_required=True,
                notes=('Personal data must not be retained indefinitely.',),
            ),
            'regulated': DataRetentionRule('regulated', RetentionPolicyLevel.REGULATED, 365 * 3),
            'regulated_pii': DataRetentionRule(
                'regulated_pii',
                RetentionPolicyLevel.REGULATED,
                365 * 3,
                hard_delete_required=True,
            ),
            'secrets': DataRetentionRule(
                'secrets',
                RetentionPolicyLevel.SHORT,
                7,
                hard_delete_required=True,
                notes=('Secret-bearing payloads require aggressive minimization.',),
            ),
            'audit_immutable': DataRetentionRule('audit_immutable', RetentionPolicyLevel.IMMUTABLE_AUDIT, 365 * 7),
        }
        self._rules = dict(base_rules)
        if rules:
            self._rules.update(rules)

    def get_rule(self, profile: str) -> DataRetentionRule:
        if not profile.strip():
            raise ComplianceValidationError('Retention profile must be non-empty.')
        return self._rules.get(profile, self._rules['internal_default'])

    def evaluate(
        self,
        *,
        profile: str,
        created_at: Optional[datetime] = None,
        legal_hold: bool = False,
    ) -> RetentionDecision:
        created_at = created_at or datetime.now(timezone.utc)
        rule = self.get_rule(profile)

        reasons = list(rule.notes)
        if legal_hold:
            if rule.legal_hold_supported:
                reasons.append('Legal hold applied.')
            else:
                reasons.append('Legal hold requested but unsupported for this profile.')

        return RetentionDecision(
            profile=rule.profile,
            level=rule.level,
            created_at=created_at,
            retain_until=created_at + timedelta(days=rule.retention_days),
            legal_hold_applied=legal_hold and rule.legal_hold_supported,
            hard_delete_required=rule.hard_delete_required,
            reasons=tuple(reasons),
            policy=self._policy,
        )
    decide = evaluate
