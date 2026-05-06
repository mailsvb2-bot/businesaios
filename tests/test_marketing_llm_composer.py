import pytest

from core.llm import MockLLMClient
from core.marketing.llm_composer import MarketingLLMComposer, LLMComposerConfig
from core.marketing.llm_prompting import MarketingLLMInputs


def test_composer_returns_text_and_caches():
    llm = MockLLMClient(fixed_text="Хочешь продолжить? Есть «Сеанс» за 990₽. Нажми «Открыть». ")
    c = MarketingLLMComposer(llm, LLMComposerConfig(model="mock"))
    inp = MarketingLLMInputs(
        tenant_id="t1",
        user_id="u1",
        locale="ru",
        channel="telegram",
        features={"segment": "warm"},
        offer={"id": "o1", "title": "Сеанс", "price": 990, "currency": "₽", "what_user_gets": "12 минут"},
        last_user_text="мой телефон +31 6 1234 5678",
    )
    t1 = c.compose_sync(inp)
    t2 = c.compose_sync(inp)
    assert t1
    assert t2 == t1


def test_composer_rejects_forbidden_phrase():
    llm = MockLLMClient(fixed_text="Я DecisionCore и я решил…")
    c = MarketingLLMComposer(llm, LLMComposerConfig(model="mock"))
    inp = MarketingLLMInputs(
        tenant_id="t1",
        user_id="u1",
        locale="ru",
        channel="telegram",
        features={},
        offer={"id": "o1", "title": "Сеанс"},
        last_user_text="",
    )
    t = c.compose_sync(inp)
    assert t is None