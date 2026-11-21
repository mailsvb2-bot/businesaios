"""Regression: canonical v2 reservation CAS must not reuse an old state identity."""

import pytest

from core.llm.budget import EventStoreDailyTokenBudget


def test_pending_v2_aba_changes_revision_even_when_rows_return_to_same_value():
    next_state = EventStoreDailyTokenBudget._next_v2_state
    original = {"pending": {}}
    reserved = next_state(original, {"req": {"user_id": "u", "tokens": 1, "day": "2026-11-21"}})
    released = next_state(reserved, {})
    assert released["pending"] == original["pending"]
    assert released != original
    assert released["revision"] == 2
    assert next_state(released, {"req2": {"user_id": "u", "tokens": 1}})["revision"] == 3


def test_pending_v2_revision_legacy_compatibility_and_fail_closed():
    next_state = EventStoreDailyTokenBudget._next_v2_state
    assert next_state(None, {}) == {"revision": 1, "pending": {}}
    assert next_state({"pending": {}}, {}) == {"revision": 1, "pending": {}}
    for invalid in (-1, True, "3", 1.5, None):
        with pytest.raises(ValueError, match="LLM_BUDGET_CORRUPT_REVISION"):
            next_state({"revision": invalid, "pending": {}}, {})


def test_pending_v2_cas_rejects_stale_pre_aba_snapshot():
    next_state = EventStoreDailyTokenBudget._next_v2_state
    current = {"pending": {}}
    snapshot = dict(current)
    current = next_state(current, {"a": {"user_id": "u", "tokens": 1}})
    current = next_state(current, {})
    assert current["pending"] == snapshot["pending"]
    assert current != snapshot  # compare_and_set_setting must reject stale expected
