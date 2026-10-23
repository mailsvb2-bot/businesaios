from __future__ import annotations

import pytest

from application.business_flows import yandex_growth as yg


def _arm(v, leads, bookings, bps):
    return {"variant_id": v, "publication_job_id": f"j{v}", "allocation_bps": bps, "leads": leads, "bookings": bookings, "won": 0}


def test_ready_moves_bounded_step_and_keeps_floor():
    r = yg.creative_allocation([_arm("a", 100, 40, 5000), _arm("b", 100, 5, 5000)], running=True)
    assert r["status"] == "ready" and r["winner_variant_id"] == "a"
    assert dict(r["allocations"]) == {"ja": 6000, "jb": 4000}
    r = yg.creative_allocation([_arm("a", 100, 40, 9000), _arm("b", 100, 5, 1000)], running=True)
    assert r["status"] == "exploration_floor_reached"


def test_guards():
    two = [_arm("a", 100, 40, 5000), _arm("b", 100, 5, 5000)]
    assert yg.creative_allocation(two, running=False)["status"] == "not_running"
    assert yg.creative_allocation([_arm("a", 10, 4, 5000), _arm("b", 100, 5, 5000)], running=True)["status"] == "insufficient_data"
    assert yg.creative_allocation([_arm("a", 100, 12, 5000), _arm("b", 100, 10, 5000)], running=True)["status"] == "no_clear_winner"
    assert yg.creative_allocation([dict(two[0], scope="campaign"), two[1]], running=True)["status"] == "attribution_not_ready"
    with pytest.raises(ValueError):
        yg.creative_allocation([_arm("a", 100, 140, 5000), two[1]], running=True)
    with pytest.raises(ValueError):
        yg.creative_allocation(two, running=True, metric="clicks")
