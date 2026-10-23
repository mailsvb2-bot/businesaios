import pytest

from application.business_flows import partners as pt

P = pt.Partner("p1", "Школа", ("йога",), 1000, "public", "@school")


def test_pitch_has_ready_post_topic_and_bounds() -> None:
    pack = pt.pitch(P, business="Студия  Лотос", offer="Вебинар по дыханию", url="https://x.example/e", topic="сон")
    assert "«сон»" in pack["outreach"] and "Студия Лотос" in pack["outreach"]
    assert pack["ready_post"].startswith("Вебинар по дыханию") and "https://x.example/e" in pack["ready_post"]
    assert pack["cta"] == "Подробнее: https://x.example/e"
    assert "ready_post" in pt.pitch(P, business="B", offer="")


@pytest.mark.parametrize(
    ("pack", "code"),
    [
        ({"outreach": "без побочных эффектов"}, "partner_copy_forbidden_claim"),
        ({"outreach": "a!b!c!d!"}, "partner_copy_too_promotional"),
        ({"outreach": "Давно слежу за вами"}, "partner_copy_invented_familiarity"),
    ],
)
def test_validate_pitch_rejects(pack, code) -> None:
    with pytest.raises(ValueError, match=code):
        pt.validate_pitch(pack)


def test_pitch_rejects_forbidden_offer() -> None:
    with pytest.raises(ValueError):
        pt.pitch(P, business="B", offer="вылечим за день")
