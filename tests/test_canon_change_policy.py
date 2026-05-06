from canon import (
    CHANGE_POLICY_FORBIDDEN_PATTERNS,
    CHANGE_POLICY_RULES,
    CHANGE_POLICY_VERSION,
    verify_change_policy_loaded,
)


def test_change_policy_is_loaded() -> None:
    assert CHANGE_POLICY_VERSION == 'V1'
    assert CHANGE_POLICY_RULES['declarative_audit_forbidden'] is True
    assert CHANGE_POLICY_RULES['direct_project_fixes_only'] is True
    assert verify_change_policy_loaded() is True


def test_change_policy_forbidden_patterns_cover_declarative_audit() -> None:
    assert 'declarative audit' in CHANGE_POLICY_FORBIDDEN_PATTERNS
