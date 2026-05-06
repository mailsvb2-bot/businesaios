from __future__ import annotations

from canon import CHANGE_POLICY_RULES, verify_change_policy_loaded


def test_canon_change_policy_requires_direct_systemic_fixes() -> None:
    assert CHANGE_POLICY_RULES['declarative_audit_forbidden'] is True
    assert CHANGE_POLICY_RULES['deep_multilayer_verification_required'] is True
    assert CHANGE_POLICY_RULES['verify_to_last_file_required'] is True
    assert CHANGE_POLICY_RULES['direct_project_fixes_only'] is True
    assert CHANGE_POLICY_RULES['systemic_canonical_fix_only'] is True
    assert CHANGE_POLICY_RULES['fix_immediately_when_found'] is True
    assert verify_change_policy_loaded() is True
