from interfaces.llm import TemplatedLLM
from core.growth.ads.creative import generate_candidates, select_creative
from core.growth.ads.creative.models import CreativeGuardrails


def test_generate_and_select_smoke():
    llm = TemplatedLLM()
    g = CreativeGuardrails()
    cands = generate_candidates(
        offer_arm="offer_std_test",
        business_type="Стоматология",
        offer_title="Осмотр + план лечения",
        offer_details="Быстро и без навязывания. Запись онлайн.",
        llm=llm,
        n=3,
        guardrails=g,
    )
    assert len(cands) >= 1
    sel = select_creative(candidates=cands, guardrails=g)
    assert sel.selected.creative_id
    assert len(sel.selected.headline) <= g.max_headline_len
    assert len(sel.selected.primary_text) <= g.max_primary_text_len
    assert len(sel.selected.description) <= g.max_description_len
