from __future__ import annotations

from datetime import datetime, timezone

import pytest

from compliance.base import ComplianceValidationError
from compliance.data_retention_policy import DataRetentionPolicy, RetentionPolicyLevel


def test_data_retention_policy_returns_expected_profile_behavior() -> None:
    policy = DataRetentionPolicy()
    created_at = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)

    decision = policy.decide(profile='regulated_pii', created_at=created_at, legal_hold=True)

    assert decision.level is RetentionPolicyLevel.REGULATED
    assert decision.legal_hold_applied is True
    assert decision.hard_delete_required is True
    assert decision.retain_until > created_at
    assert decision.policy.policy_name == 'data_retention_policy'


def test_data_retention_policy_rejects_blank_profile() -> None:
    policy = DataRetentionPolicy()

    with pytest.raises(ComplianceValidationError):
        policy.get_rule('   ')


def test_data_retention_policy_falls_back_to_internal_default_for_unknown_profile() -> None:
    policy = DataRetentionPolicy()

    decision = policy.decide(profile='unknown_profile')

    assert decision.profile == 'internal_default'
    assert decision.level is RetentionPolicyLevel.STANDARD


def test_data_retention_policy_reports_unsupported_legal_hold_without_faking_application() -> None:
    from compliance.data_retention_policy import DataRetentionRule

    policy = DataRetentionPolicy(rules={'ephemeral': DataRetentionRule('ephemeral', RetentionPolicyLevel.SHORT, 1, legal_hold_supported=False)})
    decision = policy.decide(profile='ephemeral', legal_hold=True)

    assert decision.legal_hold_applied is False
    assert any('unsupported' in reason.lower() for reason in decision.reasons)
