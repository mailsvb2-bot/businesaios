"""Dirac-Ring operators for Behavioral OS. Composes params, math, impulse."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from core.behavior.complex4 import Complex4
from core.behavior.dirac_operator_keys import required_operator_keys
from core.behavior.dirac_operator_math import apply_diag_impulse, clamp, clamp01, mix
from core.behavior.dirac_operator_params import is_operator_allowed, resolve_operator_params
from core.behavior.impulse_contract import impulse_for_event
from core.observability.silent import swallow
from core.retention.event_types import normalize_event_type


@dataclass(frozen=True)
class OperatorResult:
    psi: Complex4
    anti: float


def apply_event_operator(
    *,
    psi: Complex4,
    anti: float,
    event: Mapping[str, Any],
    context: Mapping[str, Any] | None = None,
) -> OperatorResult:
    """Apply canonical operator based on event_type."""
    ctx = context if isinstance(context, dict) else dict(context or {})
    et = normalize_event_type(str(event.get("event_type") or ""))

    if not is_operator_allowed(event_type=et, ctx=ctx):
        return OperatorResult(psi=psi, anti=float(clamp01(float(anti))))

    params = resolve_operator_params(ctx)

    dI, dT, dV, dP, dA = impulse_for_event(event)

    scale = 1.0
    try:
        dom = str(params.get("domain") or "").strip()
        scale = float(params.get("catalog").scale_for(event_type=et, domain=dom))
    except Exception:
        scale = 1.0

    try:
        es = params.get("event_scales")
        if isinstance(es, Mapping) and str(et).lower() in es:
            scale *= float(es[str(et).lower()])
    except Exception:
        swallow(__name__, "core/behavior/dirac_operators.py")

    scale = float(clamp(scale, 0.25, 3.0))
    dI = float(clamp(dI * scale, -0.35, 0.35))
    dT = float(clamp(dT * scale, -0.35, 0.35))
    dV = float(clamp(dV * scale, -0.35, 0.35))
    dP = float(clamp(dP * scale, -0.35, 0.35))
    dA = float(clamp(dA * scale, -0.25, 0.25))

    anti = clamp01(float(anti) + float(dA))
    phase_gain = float(params.get("phase_gain", 0.25))

    cur = apply_diag_impulse(psi, (dI, dT, dV, dP), phase_gain)

    k_tp = float(params.get("k_tp", 0.08))
    k_vp = float(params.get("k_vp", 0.06))
    k_it = float(params.get("k_it", 0.04))
    cur = mix(cur, 1, 3, k_tp)
    cur = mix(cur, 2, 3, k_vp)
    cur = mix(cur, 0, 1, k_it)

    if et == "paywall_closed":
        anti = clamp01(anti + 0.01)

    if anti > 0.0:
        drain = float(params.get("anti_drain", 0.15)) * float(anti)
        re = list(cur.re)
        im = list(cur.im)
        re[1] *= (1.0 - drain)
        im[1] *= (1.0 - drain)
        re[3] *= (1.0 - drain)
        im[3] *= (1.0 - drain)
        cur = Complex4(tuple(re), tuple(im)).renormalize(target_norm=1.0)

    return OperatorResult(psi=cur, anti=float(anti))


__all__ = ["apply_event_operator", "OperatorResult", "required_operator_keys"]
