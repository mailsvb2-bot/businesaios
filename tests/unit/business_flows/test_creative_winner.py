import pytest

from application.business_flows import creative_winner as cw


def _trial(rev=3, b2=10):
    return {"trial_id": "t1", "revision": rev, "running": True, "date_from": "2026-09-24", "date_to": "2026-10-23",
            "arms": [{"variant_id": "a", "publication_job_id": "j1", "allocation_bps": 5000, "leads": 200,
                      "bookings": 120, "won": 10},
                     {"variant_id": "b", "publication_job_id": "j2", "allocation_bps": 5000, "leads": 200,
                      "bookings": b2, "won": 1}]}


def test_preview_is_deterministic_and_evidence_bound():
    p = cw.preview(_trial())
    assert p["recommendation"]["status"] == "ready" and p["recommendation"]["winner_variant_id"] == "a"
    assert p["fingerprint"] == cw.preview(_trial())["fingerprint"]
    assert p["fingerprint"] != cw.preview(_trial(b2=11))["fingerprint"]
    assert p["fingerprint"] != cw.preview(_trial(), max_shift_bps=500)["fingerprint"]


def test_apply_requires_confirmation_revision_and_fingerprint():
    fp = cw.preview(_trial())["fingerprint"]
    fact = cw.apply(_trial(), expected_revision=3, expected_fingerprint=fp, confirmed=True)
    assert fact["revision"] == 4 and fact["allocations"] == [["j1", 6000], ["j2", 4000]]
    with pytest.raises(cw.CreativeWinnerApplyError, match="confirmation"):
        cw.apply(_trial(), expected_revision=3, expected_fingerprint=fp, confirmed=False)
    with pytest.raises(cw.CreativeWinnerApplyError, match="stale"):
        cw.apply(_trial(rev=4), expected_revision=3, expected_fingerprint=fp, confirmed=True)
    with pytest.raises(cw.CreativeWinnerApplyError, match="changed"):
        cw.apply(_trial(b2=11), expected_revision=3, expected_fingerprint=fp, confirmed=True)
    t = _trial(b2=118)
    with pytest.raises(cw.CreativeWinnerApplyError, match="not actionable"):
        cw.apply(t, expected_revision=3, expected_fingerprint=cw.preview(t)["fingerprint"], confirmed=True)
