from __future__ import annotations

import pytest

from application.business_autonomy.support_case_contract import (
    SupportCaseCategory,
    normalize_support_case_id,
    normalize_support_category,
    normalize_support_summary,
)


def test_support_case_categories_and_uuid_are_canonical():
    assert normalize_support_category("billing") is SupportCaseCategory.BILLING
    assert normalize_support_case_id("9FE8F704-A90D-422B-9005-FD3D81C76D23") == "9fe8f704-a90d-422b-9005-fd3d81c76d23"
    for value in ("invalid", "", None):
        with pytest.raises(ValueError):
            normalize_support_case_id(value)
    with pytest.raises(ValueError):
        normalize_support_category("platform_admin")


def test_support_case_summary_normalizes_without_leaking_credentials():
    assert normalize_support_summary("   Не    приходят\n сообщения   ") == "Не приходят сообщения"
    for value in (None, ["not a string"], "", "ab", "x" * 1001):
        with pytest.raises(ValueError):
            normalize_support_summary(value)
    secrets = (
        "api_key: abcdefghijklmnopqrstuvwxyz",
        "access_token=abcdefghijk",
        "пароль: abcdefghijkl",
        "bearer abcdefghijklmnopq",
        "123456789:ABCDEFGHIJKLMNOPQRSTUVWX",
        "eyJabcdefghijk.abcdefghijklm.abcdefghijklm",
    )
    for value in secrets:
        with pytest.raises(ValueError, match="credentials"):
            normalize_support_summary("Проблема: " + value)
