import pytest

from application.business_flows import creative_trials as ct

F = [
    {"step": "trial_recorded", "trial_id": "AAAAAA11-1", "trial": {"revision": 1}, "at_ms": 1},
    {"step": "trial_recorded", "trial_id": "aaaaaa22-2", "trial": {"revision": 1}, "at_ms": 2},
    {"step": "trial_recorded", "trial_id": "bbbbbb33-3", "trial": {"revision": 1}, "at_ms": 3},
    {"step": "trial_updated", "trial_id": "aaaaaa11-1", "changes": {"revision": 2}, "at_ms": 9},
    {"step": "trial_updated", "trial_id": "zzz", "changes": {}, "at_ms": 9},
]


def test_list_orders_by_update_and_pages() -> None:
    t = ct.replay(F)
    assert [x["trial_id"] for x in ct.list_trials(t, role="analyst")] == ["aaaaaa11-1", "bbbbbb33-3", "aaaaaa22-2"]
    assert t["aaaaaa11-1"]["revision"] == 2
    page, more = ct.list_page(t, role="owner", limit=2)
    assert len(page) == 2 and more
    assert ct.list_page(t, role="owner", limit=2, offset=2)[1] is False
    for bad in ({"limit": 0}, {"limit": True}, {"offset": -1}):
        with pytest.raises(ValueError):
            ct.list_page(t, role="owner", **bad)


def test_reference_unique_prefix_and_viewer_role() -> None:
    t = ct.replay(F)
    assert ct.resolve_reference(t, role="owner", reference="BBBBBB") == "bbbbbb33-3"
    for ref in ("aaaaaa", "abc", "xyzxyz", "cccccc"):
        with pytest.raises(ValueError):
            ct.resolve_reference(t, role="owner", reference=ref)
    with pytest.raises(Exception):
        ct.list_trials(t, role="customer")
