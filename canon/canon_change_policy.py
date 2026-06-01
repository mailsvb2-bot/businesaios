"""Canonical change policy.

This module locks the project-wide rule that architecture work is valid only when it
performs deep multilayer verification and direct systemic fixes in the codebase.
"""

from __future__ import annotations

CHANGE_POLICY_VERSION = 'V1'

CHANGE_POLICY_RULES = {
    'declarative_audit_forbidden': True,
    'deep_multilayer_verification_required': True,
    'verify_to_last_file_required': True,
    'full_cross_direction_analysis_required': True,
    'direct_project_fixes_only': True,
    'systemic_canonical_fix_only': True,
    'new_feature_must_be_visible_in_admin': True,
    'fix_immediately_when_found': True,
    'preserve_and_improve_functionality': True,
}

CHANGE_POLICY_FORBIDDEN_PATTERNS = (
    'declarative audit',
    'report without direct project fixes',
    'temporary workaround instead of canonical fix',
    'partial scan presented as full audit',
)


def verify_change_policy_loaded() -> bool:
    required_true = (
        'declarative_audit_forbidden',
        'deep_multilayer_verification_required',
        'verify_to_last_file_required',
        'full_cross_direction_analysis_required',
        'direct_project_fixes_only',
        'systemic_canonical_fix_only',
        'new_feature_must_be_visible_in_admin',
        'fix_immediately_when_found',
        'preserve_and_improve_functionality',
    )
    for key in required_true:
        if not CHANGE_POLICY_RULES.get(key):
            raise RuntimeError(f'Canon change policy not enforced: {key}')
    return True
