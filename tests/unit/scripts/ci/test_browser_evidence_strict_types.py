from __future__ import annotations

from scripts.ci import browser_evidence


def test_browser_evidence_rejects_lossy_integer_coercion() -> None:
    assert browser_evidence._integer(0) == 0
    assert browser_evidence._integer(31) == 31
    assert browser_evidence._integer("5") == 5
    assert browser_evidence._integer(-0.5) == -1
    assert browser_evidence._integer(1.25) == -1
    assert browser_evidence._integer(True) == -1
    assert browser_evidence._integer("1.0") == -1


def test_browser_evidence_requires_real_timestamp_strings() -> None:
    assert browser_evidence._timestamp("2026-08-11T10:48:09.726Z") is True
    assert browser_evidence._timestamp("2026-08-11T10:48:09+00:00") is True
    assert browser_evidence._timestamp({"not": "a timestamp"}) is False
    assert browser_evidence._timestamp(123) is False
    assert browser_evidence._timestamp("not-a-timestamp") is False
