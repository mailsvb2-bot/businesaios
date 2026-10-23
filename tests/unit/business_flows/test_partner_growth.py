import pytest

from application.business_flows import partners as pt


def test_fallback_terms():
    assert pt.fallback_terms("Йога, медитация для офиса", ["Курс дыхания"]) == ("медитация", "офиса", "дыхания")
    assert pt.fallback_terms("", []) == ("бизнес",)


def test_prepare_run_filters_and_packs():
    seen = {}

    def disc(terms, limit):
        seen["terms"], seen["limit"] = terms, limit
        return ["Йога клуб | йога, медитация | 8000 | opted_in | @yc", "Конкурент | йога | 9000 | public | @c | competitor"]

    facts = pt.prepare_run(disc, goal_terms=[], activity="йога медитация", offerings=["Курс"], business="Студия", limit=5)
    assert seen == {"terms": ["медитация"], "limit": 5}
    assert [f["step"] for f in facts] == ["partner_added", "partner_pack_prepared"]
    assert facts[1]["pack"]["subject"].endswith("Йога клуб")


def test_prepare_run_guards():
    with pytest.raises(ValueError, match="not_configured"):
        pt.prepare_run(None, goal_terms=["a"], activity="", offerings=[], business="b")
    with pytest.raises(ValueError, match="policy"):
        pt.prepare_run(lambda t, n: [], goal_terms=["a"], activity="", offerings=[], business="b", min_fit=101)
