import pytest

from application.business_flows import ladder as ld
from application.business_flows import sales as sl
from application.business_flows import sales_orchestration as so

STEPS = [ld.Step("s1", 1, "diagnostic", "Диагностика", 0.3), ld.Step("s2", 2, "audit", "Аудит", 0.8)]


def state(**kw):
    return sl.State(leads={"L": sl.Lead("L", "Ann", customer_id="c1", **kw)})


def test_signal_plan_candidate_and_replay():
    st = state()
    out = so.orchestrate(
        st, lead_id="L", event="contact", dedupe_key="k1", seen=set(), model_confidence=0.9, steps=STEPS
    )
    assert out.applied and out.stage == sl.Stage.ENGAGED and out.plan.action_kind == "ask_qualification"
    assert out.candidate.step_id == "s1" and out.plan.requires_approval
    payloads = list(out.facts)
    again = so.orchestrate(
        st, lead_id="L", event="contact", dedupe_key="k1", seen=so.seen_signals(payloads), model_confidence=0.9
    )
    assert not again.applied and again.facts == ()


def test_handoff_paths():
    st = state()
    low = so.orchestrate(
        st, lead_id="L", event="contact", dedupe_key="a", seen=set(), model_confidence=0.5, steps=STEPS
    )
    assert low.plan.action_kind == "human_handoff" and low.handoff.reason == "low_confidence" and low.candidate is None
    price = so.orchestrate(
        st, lead_id="L", event="contact", dedupe_key="b", seen=set(), model_confidence=0.9, pricing_exception=True
    )
    assert price.plan.rationale == "handoff:pricing_exception"
    assert (
        so.evaluate_handoff(model_confidence=0.9, sensitive_context=True, explicit_human_request=True).severity
        == "urgent"
    )
    assert so.evaluate_handoff(model_confidence=0.9, failed_attempts=2).reason == "repeated_failure"
    with pytest.raises(ValueError):
        so.evaluate_handoff(model_confidence=float("nan"))
    with pytest.raises(ValueError):
        so.bounded_score(float("inf"))


def test_approval_gate():
    st = state()
    out = so.orchestrate(st, lead_id="L", event="contact", dedupe_key="k", seen=set(), model_confidence=0.9)
    facts = list(out.facts)
    with pytest.raises(PermissionError):
        so.authorize_outbound(facts, st, out.plan.plan_id)
    facts.append(so.approve_plan(facts, out.plan.plan_id))
    auth = so.authorize_outbound(facts, st, out.plan.plan_id)
    assert auth["customer_id"] == "c1" and auth["action_kind"] == "ask_qualification"
    with pytest.raises(PermissionError):
        so.authorize_outbound(facts, state(followup_suppressed=True), out.plan.plan_id)


def test_closed_lead_noop():
    assert so.plan_action(sl.Lead("L", "a", stage=sl.Stage.WON), model_confidence=1.0) == ("noop", "lead_is_closed")
    assert so.plan_action(sl.Lead("L", "a"), model_confidence=1.0)[0] == "ask_qualification"
    assert so.plan_action(sl.Lead("L", "a", customer_id="c"), model_confidence=1.0)[0] == "respond"
