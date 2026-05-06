from core.llm.guardrails_ext import enforce_price_exact, forbid_manipulation_claims


def test_forbid_urgency():
    r = forbid_manipulation_claims("Только сегодня! Срочно покупай.")
    assert not r.ok


def test_price_exact():
    ok = enforce_price_exact("Сеанс за 990₽. Нажми открыть.", price="990", currency="₽")
    bad = enforce_price_exact("Сеанс за 990. Нажми открыть.", price="990", currency="₽")
    assert ok.ok
    assert not bad.ok
