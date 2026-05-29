from __future__ import annotations

"""Dirac-inspired behavioral dynamics (BusinesAIOS core).

Deterministic, bounded, product-agnostic.

We model a client as a 4-component *complex* state (spinor):

  psi = (I, T, V, P)

I: intent/need
T: trust/risk
V: value recognition
P: payment readiness

Complex numbers are stored as (re, im) for speed and determinism.
"""

import math
from typing import Any, Dict, Iterable, Mapping, Tuple

from core.behavior.complex4 import EPS, Complex4
from core.behavior.dirac_operators import apply_event_operator
from core.observability.silent import swallow


def _clamp01(x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    return float(x)


def _decay(dt_s: float, half_life_s: float) -> float:
    dt_s = max(0.0, float(dt_s))
    hl = max(1.0, float(half_life_s))
    return float(math.exp(-0.6931471805599453 * dt_s / hl))


class DiracBehaviorModel:
    def __init__(self, *, half_life_s: float = 6 * 3600.0):
        self._half_life_s = float(half_life_s)

    def evolve(
        self,
        *,
        psi: Complex4,
        events: Iterable[Mapping[str, Any]],
        now_ms: int | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> tuple[Complex4, dict[str, Any]]:
        # ctx intentionally mutable for operator layer audit signals.
        ctx: dict[str, Any] = context if isinstance(context, dict) else dict(context or {})
        evs = [e for e in events if isinstance(e, Mapping)]
        evs = sorted(evs, key=lambda x: int(x.get("timestamp_ms") or 0))
        ts_now = int(now_ms) if now_ms is not None else (int(evs[-1].get("timestamp_ms") or 0) if evs else 0)
        prev_ts = None

        anti = float(ctx.get("anti") or 0.0)
        anti = max(0.0, min(1.0, anti))

        cur = psi
        for e in evs:
            ts = int(e.get("timestamp_ms") or 0)
            if prev_ts is not None and ts >= prev_ts:
                dt_s = (ts - prev_ts) / 1000.0
                d = _decay(dt_s, self._half_life_s)
                cur = Complex4(tuple(float(x * d) for x in cur.re), tuple(float(x * d) for x in cur.im))
                anti *= d
            prev_ts = ts

            r = apply_event_operator(psi=cur, anti=anti, event=e, context=ctx)
            cur = r.psi
            anti = float(r.anti)

        if now_ms is not None and prev_ts is not None and int(now_ms) > int(prev_ts):
            dt_s = (int(now_ms) - int(prev_ts)) / 1000.0
            d = _decay(dt_s, self._half_life_s)
            cur = Complex4(tuple(float(x * d) for x in cur.re), tuple(float(x * d) for x in cur.im))
            anti *= d

        obs: dict[str, Any] = self.observables(psi=cur, anti=anti, now_ms=ts_now)
        # Attach optional audit fields (best-effort).
        try:
            den = ctx.get("policy_denials")
            if isinstance(den, dict) and den:
                obs["policy_denials"] = {str(k): int(v) for k, v in den.items()}
        except Exception:
            swallow(__name__, 'core/behavior/dirac_behavior.py')
        try:
            if bool(ctx.get("guardrails_violation")):
                obs["guardrails_violation"] = True
        except Exception:
            swallow(__name__, 'core/behavior/dirac_behavior.py')
        return cur, obs

    def observables(self, *, psi: Complex4, anti: float, now_ms: int) -> dict[str, float]:
        n2 = psi.norm2()
        engagement = _clamp01(math.sqrt(max(0.0, n2)))

        amps = [math.sqrt(max(0.0, (a * a + b * b))) for a, b in zip(psi.re, psi.im, strict=False)]
        s = sum(amps) + EPS
        intent = float(amps[0] / s)
        trust = float(amps[1] / s)
        value = float(amps[2] / s)
        pay = float(amps[3] / s)

        ph = psi.phases()
        mx = sum(math.cos(x) for x in ph) / 4.0
        my = sum(math.sin(x) for x in ph) / 4.0
        coherence = _clamp01(math.sqrt(mx * mx + my * my))

        direction_to_buy = _clamp01(0.45 * pay + 0.30 * trust + 0.25 * value)
        fatigue = _clamp01(0.65 * float(anti) + 0.35 * (1.0 - float(coherence)) * float(engagement))
        hesitation = _clamp01(float(engagement) * (1.0 - float(direction_to_buy)))
        trust_index = _clamp01(float(trust) * (1.0 - float(anti)))
        p_buy = _clamp01((direction_to_buy ** 1.35) * (0.5 + 0.5 * coherence) * (1.0 - 0.8 * float(anti)))

        return {
            "engagement_score": float(engagement),
            "intent_index": float(intent),
            "trust_index": float(trust_index),
            "value_index": float(value),
            "payment_readiness_index": float(pay),
            "coherence": float(coherence),
            "anti": _clamp01(float(anti)),
            "direction_to_buy": float(direction_to_buy),
            "fatigue_index": float(fatigue),
            "hesitation_score": float(hesitation),
            "purchase_probability": float(p_buy),
            "ts_ms": float(int(now_ms)),
        }
