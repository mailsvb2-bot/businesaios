import pytest

from application.business_flows import bookings as bk

S = {
    "a": bk.Slot("a", "Йога", 2_000, 60, status="booked", customer_id="u1"),
    "b": bk.Slot("b", "Йога", 500, 60, status="booked", customer_id="u1"),
    "c": bk.Slot("c", "Йога", 3_000, 60),
}


def test_customer_booking_future_own_only() -> None:
    assert bk.customer_booking(S, "a", customer_id="u1", now_ms=1_000).slot_id == "a"
    for sid, cid, code in (
        ("a", "u2", "booking_not_found"),
        ("c", "u1", "booking_not_found"),
        ("b", "u1", "booking_already_started"),
        ("zz", "u1", "booking_not_found"),
    ):
        with pytest.raises(ValueError, match=code):
            bk.customer_booking(S, sid, customer_id=cid, now_ms=1_000)
    with pytest.raises(ValueError, match="customer_role_required"):
        bk.customer_booking(S, "a", customer_id="u1", now_ms=1_000, is_member=True)


def test_customer_businesses_excludes_member_businesses() -> None:
    per = {"t2": S, "t1": S, "t3": {"c": S["c"]}}
    assert bk.customer_businesses(per, customer_id="u1", member_business_ids=set()) == ["t1", "t2"]
    assert bk.customer_businesses(per, customer_id="u1", member_business_ids={"t1"}) == ["t2"]
