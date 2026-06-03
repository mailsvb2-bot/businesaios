from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping, Sequence

from core.behavior.dirac_behavior import Complex4, DiracBehaviorModel
from core.behavior.operator_catalogs import resolve_operator_context
from core.behavior.operator_policy_catalogs import OperatorPolicyContext
from core.tenancy.normalization import normalize_tenant_id


def _infer_funnel_stage(events: Sequence[Mapping[str, Any]]) -> str | None:
    """Best-effort funnel stage inference.

    Priority:
      1) explicit payload.funnel_stage / payload.stage
      2) minimal deterministic heuristic from event_type

    This is intentionally small and conservative: products should emit
    payload.funnel_stage explicitly to avoid ambiguity.
    """

    for ev in reversed(list(events or [])):
        payload = ev.get("payload") or {}
        if isinstance(payload, Mapping):
            stage = payload.get("funnel_stage") or payload.get("stage")
            if stage:
                return str(stage)

    for ev in reversed(list(events or [])):
        et = str(ev.get("event_type") or "").lower()
        if any(k in et for k in ("paywall", "checkout", "purchase")):
            return "decision"
        if "offer_" in et:
            return "consideration"
        if "onboard" in et:
            return "onboarding"
        if "retention" in et:
            return "retention"

    return None


def _infer_actor_role(events: Sequence[Mapping[str, Any]]) -> str | None:
    for ev in reversed(list(events or [])):
        payload = ev.get("payload") or {}
        if isinstance(payload, Mapping):
            role = payload.get("actor_role") or payload.get("role")
            if role:
                return str(role)
    return None


@dataclass(frozen=True)
class BehavioralStateBuilder:
    """Universal behavioral layer.

    Input: raw events and/or read-model snapshots.
    Output: behavior features that downstream DecisionCore + pricing can consume.

    Notes:
    - Deterministic.
    - No side effects.
    - Avoid "second brain": this builder does not decide, only summarizes.
    """

    def infer_policy_context(self, events: Sequence[Mapping[str, Any]]) -> OperatorPolicyContext:
        return OperatorPolicyContext(
            funnel_stage=_infer_funnel_stage(events),
            actor_role=_infer_actor_role(events),
        )

    def build(
        self,
        events: Sequence[Mapping[str, Any]],
        *,
        product: Mapping[str, Any] | None = None,
        tenant_id: str | None = None,
        policy_context: OperatorPolicyContext | None = None,
        safe_mode: bool | None = None,
    ) -> Mapping[str, Any]:
        model = DiracBehaviorModel()

        # Start from a neutral state; keep deterministic.
        # NOTE: Golden replays depend on a zero-start state.
        psi0 = Complex4.zeros()

        p = dict(product or {})
        ctx0 = resolve_operator_context(product=p, tenant_id=tenant_id)

        # Provide enough identity for catalog resolution.
        ctx0.setdefault("tenant_id", normalize_tenant_id(tenant_id))
        ctx0.setdefault("product_id", str(p.get("product_id") or p.get("id") or ""))

        # Policy context is read-only metadata.
        pol = policy_context or self.infer_policy_context(events)
        ctx0["policy_context"] = {
            "funnel_stage": pol.funnel_stage,
            "actor_role": pol.actor_role,
        }

        # Policy telemetry: the operator application path may write into this dict
        # (denied_operator_key -> count). This is purely diagnostic.
        policy_denials: dict[str, int] = {}
        ctx0["policy_denials"] = policy_denials
        ctx0["safe_mode"] = bool(safe_mode)

        # anti in context acts as a seed / clamp helper.
        ctx = {"anti": 0.0, **ctx0}
        _, obs = model.evolve(psi=psi0, events=list(events or []), now_ms=None, context=ctx)

        out: dict[str, Any] = {
            "engagement_score": float(obs.get("engagement_score", 0.0)),
            "reaction_speed_ms": None,
            "hesitation_score": float(obs.get("hesitation_score", 0.0)),
            "purchase_probability": float(obs.get("purchase_probability", 0.0)),
            "fatigue_index": float(obs.get("fatigue_index", 0.0)),
            "trust_index": float(obs.get("trust_index", 0.0)),
            "coherence": float(obs.get("coherence", 0.0)),
            "anti": float(obs.get("anti", 0.0)),
            # expose minimal context to help downstream enforcement
            "funnel_stage": pol.funnel_stage,
            "actor_role": pol.actor_role,
            "guardrails_violation": bool(obs.get("guardrails_violation")),
        }
        out["dirac"] = {
            "intent_index": float(obs.get("intent_index", 0.0)),
            "value_index": float(obs.get("value_index", 0.0)),
            "payment_readiness_index": float(obs.get("payment_readiness_index", 0.0)),
            "direction_to_buy": float(obs.get("direction_to_buy", 0.0)),
        }

        # Minimal audit payload to detect "second lines" / policy drift.
        if policy_denials:
            top = sorted(policy_denials.items(), key=lambda kv: (-int(kv[1]), str(kv[0])))[:10]
            out["policy_audit"] = {
                "denied_total": int(sum(int(v) for v in policy_denials.values())),
                "denied_by_operator": {k: int(v) for k, v in sorted(policy_denials.items())},
                "top_denied": [{"operator_key": k, "count": int(v)} for k, v in top],
            }
        return out

    def build_from_readmodel(
        self,
        snapshot: Mapping[str, Any],
        *,
        product: Mapping[str, Any] | None = None,
        tenant_id: str | None = None,
        policy_context: OperatorPolicyContext | None = None,
        safe_mode: bool | None = None,
    ) -> Mapping[str, Any]:
        """Backward-compatible adapter for existing callers.

        Some runtime paths only have a read-model snapshot (no raw events).
        We map the snapshot into a deterministic pseudo-state.
        """
        snap = dict(snapshot or {})

        anti = 0.0
        try:
            fatigue = float(snap.get("fatigue_index") or 0.0)
            trust = float(snap.get("trust_index") or 0.0)
            anti = max(0.0, min(1.0, 0.65 * fatigue + 0.35 * (1.0 - trust)))
        except Exception:
            anti = 0.0

        def _sq(x: float) -> float:
            x = float(x)
            return x / (1.0 + abs(x))

        I = _sq(float(snap.get("engagement_score") or 0.0))
        T = _sq(float(snap.get("trust_index") or 0.0))
        V = _sq(float(snap.get("value_index") or snap.get("purchase_probability") or 0.0))
        P = _sq(float(snap.get("payment_readiness_index") or 0.0))

        psi0 = Complex4((I, T, V, P), (0.0, 0.0, 0.0, 0.0)).renormalize(target_norm=1.0)
        model = DiracBehaviorModel()

        p = dict(product or {})
        ctx0 = resolve_operator_context(product=p, tenant_id=tenant_id)
        ctx0.setdefault("tenant_id", normalize_tenant_id(tenant_id))
        ctx0.setdefault("product_id", str(p.get("product_id") or p.get("id") or ""))

        pol = policy_context or OperatorPolicyContext()
        ctx0["policy_context"] = {"funnel_stage": pol.funnel_stage, "actor_role": pol.actor_role}
        ctx0["safe_mode"] = bool(safe_mode)

        ctx = {"anti": anti, **ctx0}
        _, obs = model.evolve(psi=psi0, events=[], now_ms=None, context=ctx)

        return {
            "engagement_score": float(obs.get("engagement_score", 0.0)),
            "reaction_speed_ms": None,
            "hesitation_score": float(obs.get("hesitation_score", 0.0)),
            "purchase_probability": float(obs.get("purchase_probability", 0.0)),
            "fatigue_index": float(obs.get("fatigue_index", 0.0)),
            "trust_index": float(obs.get("trust_index", 0.0)),
            "coherence": float(obs.get("coherence", 0.0)),
            "anti": float(obs.get("anti", 0.0)),
            "funnel_stage": pol.funnel_stage,
            "actor_role": pol.actor_role,
            "guardrails_violation": bool(obs.get("guardrails_violation")),
        }
