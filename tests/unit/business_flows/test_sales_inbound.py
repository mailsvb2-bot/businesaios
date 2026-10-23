import pytest

from application.business_flows import sales as sl
from application.business_flows import sales_inbound as si


def _rec(payloads, eid="1", text="Хочу записаться", ai=False):
    return si.record_message(
        payloads,
        channel="telegram",
        subject="42",
        name="Анна",
        source_ref="bot1",
        event_id=eid,
        text=text,
        ai_allowed=ai,
    )


def test_extract_and_normalize() -> None:
    assert si.extract_text({"message": {"text": "  привет\n мир "}}) == "привет мир"
    assert si.extract_text({"edited_message": {"caption": "фото"}}) == "фото"
    assert si.extract_text({"message": {"text": "/start"}}) is None
    assert si.extract_text({"callback_query": {}}) is None
    with pytest.raises(ValueError):
        si.printable("a\x01", field_name="x", maximum=5)


def test_inbound_creates_engaged_lead_idempotently_without_text_unless_ai() -> None:
    first = _rec([])
    st = sl.replay(first)
    (lead,) = st.leads.values()
    assert lead.stage == sl.Stage.ENGAGED and lead.source == "telegram" and not lead.notes
    assert _rec(first) == []
    again = _rec(first, eid="2", ai=True)
    assert [p["step"] for p in again] == ["lead_inbound", "lead_note"]
    with pytest.raises(ValueError):
        _rec([], text="/help")
    with pytest.raises(ValueError):
        si.record_message(
            [], channel="email", subject="1", name="", source_ref="s", event_id="e", text="x", ai_allowed=False
        )
