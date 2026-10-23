"""Sales signal orchestration (port of donor sales_orchestration + domain sales_handoff
evaluate_handoff + sales.plan_sales_action) over ``sales_pipeline@v1`` facts.

signal -> stage transition (sales.reduce) -> next-action plan -> optional handoff ->
optional commercial-ladder candidate. Pure: returns facts, never sends anything.
Outbound needs a separate explicit owner approval (``approve_plan``) and
``authorize_outbound`` only returns an authorization; the executor sends.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

from application.business_flows import ladder as ld
from application.business_flows import sales as sl

CONFIDENCE_THRESHOLD = 0.72
STAGE_EVIDENCE_SCORE = {
    sl.Stage.DISCOVERED: 0.10,
    sl.Stage.ENGAGED: 0.35,
    sl.Stage.NEED_KNOWN: 0.50,
    sl.Stage.QUALIFIED: 0.75,
    sl.Stage.OFFER_PRESENTED: 0.82,
    sl.Stage.CHECKOUT: 0.92,
    sl.Stage.WON: 1.00,
    sl.Stage.LOST: 0.00,
}
# donor stage -> action; bai-port stages are finer (NEED_KNOWN / OFFER_PRESENTED), mapped to nearest donor stage.
_STAGE_ACTION = {
    sl.Stage.ENGAGED: "ask_qualification",
    sl.Stage.NEED_KNOWN: "ask_qualification",
    sl.Stage.QUALIFIED: "present_offer",
    sl.Stage.OFFER_PRESENTED: "present_offer",
    sl.Stage.CHECKOUT: "checkout_followup",
}


@dataclass(frozen=True)
class HandoffSignal:
    reason: str
    severity: str
    summary: str


@dataclass(frozen=True)
class Plan:
    plan_id: str
    lead_id: str
    action_kind: str
    rationale: str
    requires_approval: bool


@dataclass(frozen=True)
class Outcome:
    stage: sl.Stage
    applied: bool
    plan: Plan | None = None
    handoff: HandoffSignal | None = None
    candidate: ld.Step | None = None
    facts: tuple[dict[str, Any], ...] = ()


def bounded_score(value: float) -> float:
    score = float(value)
    if not math.isfinite(score):
        raise ValueError("evidence_score must be finite")
    return max(0.0, min(score, 1.0))


def _confidence(value: float) -> float:
    c = float(value)
    if not math.isfinite(c):
        raise ValueError("model_confidence must be finite")
    return max(0.0, min(c, 1.0))


def evaluate_handoff(
    *,
    model_confidence: float,
    explicit_human_request: bool = False,
    sensitive_context: bool = False,
    pricing_exception: bool = False,
    negative_sentiment: bool = False,
    failed_attempts: int = 0,
) -> HandoffSignal | None:
    """Operational handoff signal; never contacts staff directly. Donor priority order."""
    for name, v in (
        ("explicit_human_request", explicit_human_request),
        ("sensitive_context", sensitive_context),
        ("pricing_exception", pricing_exception),
        ("negative_sentiment", negative_sentiment),
    ):
        if not isinstance(v, bool):
            raise ValueError(f"{name} must be a boolean")
    conf = _confidence(model_confidence)
    if isinstance(failed_attempts, bool) or not isinstance(failed_attempts, int) or failed_attempts < 0:
        raise ValueError("failed_attempts must be a non-negative integer")
    if sensitive_context:
        return HandoffSignal("sensitive_context", "urgent", "Sensitive or regulated context requires a human.")
    if explicit_human_request:
        return HandoffSignal("explicit_request", "high", "The customer explicitly requested a human.")
    if pricing_exception:
        return HandoffSignal("pricing_exception", "high", "The request falls outside the approved pricing/offer path.")
    if failed_attempts >= 2:
        return HandoffSignal("repeated_failure", "high", "Automation failed repeatedly; preserve context and hand off.")
    if negative_sentiment:
        return HandoffSignal("negative_sentiment", "normal", "Negative sentiment warrants human review.")
    if conf < CONFIDENCE_THRESHOLD:
        return HandoffSignal("low_confidence", "normal", "Model confidence is below the sales automation threshold.")
    return None


def plan_action(
    lead: sl.Lead,
    *,
    model_confidence: float,
    unanswered_inbound: bool = False,
    explicit_human_request: bool = False,
    sensitive_context: bool = False,
) -> tuple[str, str]:
    """Fail-closed next action (kind, rationale). Contact basis: inbound (has customer_id) or owner-entered."""
    conf = _confidence(model_confidence)
    if lead.stage in (sl.Stage.WON, sl.Stage.LOST):
        return "noop", "lead_is_closed"
    if explicit_human_request or sensitive_context or conf < CONFIDENCE_THRESHOLD:
        why = (
            "explicit_human_request"
            if explicit_human_request
            else "sensitive_context"
            if sensitive_context
            else "low_model_confidence"
        )
        return "human_handoff", why
    if lead.followup_suppressed:
        return "noop", "no_contact_basis"
    basis = "inbound" if lead.customer_id else "owner_entered"
    if unanswered_inbound:
        kind = "respond"
    elif lead.stage == sl.Stage.DISCOVERED:
        kind = "respond" if basis == "inbound" else "ask_qualification"
    else:
        kind = _STAGE_ACTION.get(lead.stage, "noop")
    return kind, f"stage:{lead.stage.value};basis:{basis}"


def select_candidate(steps: list[ld.Step], completed: set[str], evidence_score: float) -> ld.Step | None:
    found = ld.candidates(steps, evidence_score=evidence_score, completed=completed)
    return found[0] if found else None


def seen_signals(payloads: list[dict[str, Any]]) -> set[str]:
    return {str(p["dedupe_key"]) for p in payloads if p.get("step") == "lead_event" and p.get("dedupe_key")}


def orchestrate(
    st: sl.State,
    *,
    lead_id: str,
    event: str,
    dedupe_key: str,
    seen: set[str],
    model_confidence: float,
    steps: list[ld.Step] = (),
    completed: set[str] = frozenset(),
    unanswered_inbound: bool = False,
    explicit_human_request: bool = False,
    sensitive_context: bool = False,
    pricing_exception: bool = False,
    negative_sentiment: bool = False,
    failed_attempts: int = 0,
    evidence_score: float | None = None,
) -> Outcome:
    """Replay-safe: a repeated dedupe_key returns applied=False and no facts."""
    lead = st.leads.get(lead_id)
    if lead is None:
        raise ValueError("lead_not_found")
    if dedupe_key in seen:
        return Outcome(lead.stage, False)
    stage = sl.reduce(lead.stage, event)
    facts: list[dict[str, Any]] = [
        {"step": "lead_event", "lead_id": lead.lead_id, "event": event, "stage": stage.value, "dedupe_key": dedupe_key}
    ]
    moved = replace(lead, stage=stage)
    signal = evaluate_handoff(
        model_confidence=model_confidence,
        explicit_human_request=explicit_human_request,
        sensitive_context=sensitive_context,
        pricing_exception=pricing_exception,
        negative_sentiment=negative_sentiment,
        failed_attempts=failed_attempts,
    )
    pid = f"plan:{dedupe_key}"
    if (
        signal is not None
        and not explicit_human_request
        and not sensitive_context
        and float(model_confidence) >= CONFIDENCE_THRESHOLD
    ):
        kind, why = "human_handoff", f"handoff:{signal.reason}"
    else:
        kind, why = plan_action(
            moved,
            model_confidence=model_confidence,
            unanswered_inbound=unanswered_inbound,
            explicit_human_request=explicit_human_request,
            sensitive_context=sensitive_context,
        )
    plan = Plan(pid, lead.lead_id, kind, why, kind not in ("noop", "human_handoff"))
    facts.append(
        {
            "step": "sales_plan_saved",
            "plan_id": pid,
            "lead_id": lead.lead_id,
            "action_kind": kind,
            "rationale": why,
            "requires_approval": plan.requires_approval,
        }
    )
    if signal is not None:
        facts.append(
            {
                "step": "lead_event",
                "lead_id": lead.lead_id,
                "event": "handoff",
                "stage": stage.value,
                "reason": signal.reason,
                "severity": signal.severity,
                "plan_id": pid,
            }
        )
    cand = None
    if kind not in ("noop", "human_handoff"):
        score = bounded_score(STAGE_EVIDENCE_SCORE[stage] if evidence_score is None else evidence_score)
        cand = select_candidate(list(steps), set(completed), score)
        if cand is not None:
            facts.append(
                {
                    "step": "commercial_candidate_selected",
                    "lead_id": lead.lead_id,
                    "plan_id": pid,
                    "step_id": cand.step_id,
                    "kind": cand.kind,
                    "title": cand.title,
                    "requires_human_approval": cand.requires_approval,
                    "evidence_score": score,
                }
            )
    return Outcome(stage, True, plan, signal, cand, tuple(facts))


def plans(payloads: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for p in payloads:
        if p.get("step") == "sales_plan_saved":
            out[str(p["plan_id"])] = {**p, "approved": False}
        elif p.get("step") == "sales_plan_approved" and p.get("plan_id") in out:
            out[str(p["plan_id"])]["approved"] = True
    return out


def approve_plan(payloads: list[dict[str, Any]], plan_id: str) -> dict[str, Any]:
    p = plans(payloads).get(plan_id)
    if p is None:
        raise ValueError("sales_plan_not_found")
    if not p["requires_approval"]:
        raise ValueError("sales_plan_not_outbound")
    return {"step": "sales_plan_approved", "plan_id": plan_id}


def authorize_outbound(payloads: list[dict[str, Any]], st: sl.State, plan_id: str) -> dict[str, Any]:
    """Authorization only after explicit approval; sending is the executor's job."""
    p = plans(payloads).get(plan_id)
    if p is None or not p["approved"]:
        raise PermissionError("sales_outbound_not_approved")
    lead = st.leads[p["lead_id"]]
    if lead.followup_suppressed or lead.stage in (sl.Stage.WON, sl.Stage.LOST) or not lead.customer_id:
        raise PermissionError("sales_outbound_not_allowed")
    return {
        "plan_id": plan_id,
        "lead_id": lead.lead_id,
        "customer_id": lead.customer_id,
        "action_kind": p["action_kind"],
    }
