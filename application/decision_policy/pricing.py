from __future__ import annotations

from typing import Any

from core.economics.economics_config import EconomicsConfigV1
from core.observability.throttled_logger import exception_throttled


def band_rank(band: str | None) -> int:
    b = str(band or '').strip().lower()
    return {'low': 0, 'standard': 1, 'premium': 2}.get(b, 1)


def allowed_price_band(*, state: Any, logger: Any) -> str:
    econ_raw = {}
    try:
        prod = getattr(state, 'product', None)
        if isinstance(prod, dict):
            er = prod.get('economics')
            if isinstance(er, dict):
                econ_raw = er
    except Exception:
        econ_raw = {}
    econ = EconomicsConfigV1.from_dict(econ_raw)

    target_cac = max(0, int(econ.target_cac_rub))
    ratio = float(econ.min_ltv_cac_ratio)

    pred_ltv = None
    try:
        eco = getattr(state, 'economy', None)
        if isinstance(eco, dict):
            v = eco.get('predicted_ltv')
            if v is not None:
                pred_ltv = float(v)
    except Exception:
        pred_ltv = None

    b = {}
    try:
        b0 = getattr(state, 'behavior', None)
        if isinstance(b0, dict):
            b = b0
    except Exception:
        b = {}

    try:
        if bool(b.get('guardrails_violation') or b.get('behavior_guardrails_violation')):
            return 'low'
    except Exception:
        exception_throttled(logger, key='decision_core.allowed_price_band.guardrails', msg='decision_core: failed to evaluate behavior guardrails flag')

    is_cold = (int(b.get('clicks_total', 0) or 0) == 0) and (int(b.get('audio_starts', 0) or 0) == 0)
    if pred_ltv is None or pred_ltv < 0:
        return 'low' if is_cold else 'standard'
    if target_cac > 0 and pred_ltv < (target_cac * ratio):
        return 'low'
    try:
        if int(b.get('audio_completions', 0) or 0) >= 1:
            return 'premium'
    except Exception:
        exception_throttled(logger, key='decision_core.allowed_price_band.audio_completions', msg='decision_core: failed to evaluate audio_completions for premium band')
    return 'standard'


def merge_price_constraints(*, base: dict | None, override: dict | None, logger: Any) -> dict:
    out: dict = {}
    if isinstance(base, dict):
        out.update(base)
    if isinstance(override, dict):
        out.update(override)
    try:
        b0 = (base or {}).get('max_band') if isinstance(base, dict) else None
        b1 = (override or {}).get('max_band') if isinstance(override, dict) else None
        if b0 or b1:
            out['max_band'] = str(b0) if band_rank(b0) <= band_rank(b1) else str(b1)
    except Exception:
        exception_throttled(logger, key='decision_core.merge_price_constraints', msg='decision_core: failed to merge price constraints')
    return out
