from __future__ import annotations

import pytest

from reliability.lease_fencing_token import LeaseFencingToken, assert_fencing_token_progression


def test_fencing_token_requires_positive_value() -> None:
    with pytest.raises(ValueError):
        LeaseFencingToken(0)
    with pytest.raises(ValueError):
        LeaseFencingToken(-1)


def test_fencing_token_parse_and_as_int() -> None:
    token = LeaseFencingToken.parse("7")
    assert token.value == 7
    assert token.as_int() == 7


def test_fencing_token_detects_stale_candidate() -> None:
    current = LeaseFencingToken(5)
    stale = LeaseFencingToken(4)
    assert stale.is_stale_against(current=current) is True
    with pytest.raises(PermissionError):
        stale.assert_not_stale_against(current=current)


def test_fencing_token_allows_equal_and_newer_candidate() -> None:
    current = LeaseFencingToken(5)
    same = LeaseFencingToken(5)
    newer = LeaseFencingToken(6)
    assert same.is_stale_against(current=current) is False
    assert newer.is_stale_against(current=current) is False
    same.assert_not_stale_against(current=current)
    newer.assert_not_stale_against(current=current)


def test_assert_fencing_token_progression_accepts_initial_candidate() -> None:
    assert_fencing_token_progression(current=None, candidate=LeaseFencingToken(1))


def test_assert_fencing_token_progression_rejects_regression() -> None:
    with pytest.raises(PermissionError):
        assert_fencing_token_progression(current=LeaseFencingToken(9), candidate=LeaseFencingToken(8))
