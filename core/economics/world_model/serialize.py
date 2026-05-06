from __future__ import annotations

from typing import Any, Dict

from .conversion import LogisticConversionModel
from .demand_curves import IsoelasticDemandCurve, LinearDemandCurve, PiecewiseLinearDemandCurve
from .seasonality import DOWSeasonalityModel
from .world_model import PricingWorldModel


def pricing_world_model_to_dict(m: PricingWorldModel) -> Dict[str, Any]:
    out: Dict[str, Any] = {"kind": "pricing_world_model@v1"}

    d = m.demand
    if isinstance(d, IsoelasticDemandCurve):
        out["demand"] = {"type": "isoelastic", "a": d.a, "b": d.b}
    elif isinstance(d, LinearDemandCurve):
        out["demand"] = {"type": "linear", "a": d.a, "b": d.b}
    elif isinstance(d, PiecewiseLinearDemandCurve):
        out["demand"] = {"type": "piecewise_linear", "breakpoints": list([list(x) for x in d.breakpoints])}
    else:
        out["demand"] = {"type": d.__class__.__name__}

    c = m.conversion
    if isinstance(c, LogisticConversionModel):
        out["conversion"] = {"type": "logistic", "w0": c.w0, "w1": c.w1, "l2": c.l2}
    else:
        out["conversion"] = {"type": c.__class__.__name__}

    s = m.seasonality
    if isinstance(s, DOWSeasonalityModel):
        out["seasonality"] = {"type": "dow", "mult": dict(s.mult)}
    else:
        out["seasonality"] = {"type": s.__class__.__name__}

    return out


def pricing_world_model_from_dict(d: Dict[str, Any]) -> PricingWorldModel:
    d = dict(d or {})
    demand_d = dict(d.get("demand") or {})
    conv_d = dict(d.get("conversion") or {})
    seas_d = dict(d.get("seasonality") or {})

    # demand
    dt = str(demand_d.get("type") or "isoelastic")
    if dt == "linear":
        demand = LinearDemandCurve(a=float(demand_d.get("a", 1.0)), b=float(demand_d.get("b", -0.01)))
    elif dt == "piecewise_linear":
        bps = demand_d.get("breakpoints") or []
        pts = []
        for x in bps:
            try:
                pts.append((float(x[0]), float(x[1])))
            except Exception:
                continue
        demand = PiecewiseLinearDemandCurve(breakpoints=tuple(pts))
    else:
        demand = IsoelasticDemandCurve(a=float(demand_d.get("a", 1.0)), b=float(demand_d.get("b", -1.0)))

    # conversion
    ct = str(conv_d.get("type") or "logistic")
    if ct == "logistic":
        conv = LogisticConversionModel(w0=float(conv_d.get("w0", -2.0)), w1=float(conv_d.get("w1", -0.01)), l2=float(conv_d.get("l2", 1e-6)))
    else:
        conv = LogisticConversionModel(w0=-2.0, w1=-0.01, l2=1e-6)

    # seasonality
    st = str(seas_d.get("type") or "dow")
    if st == "dow":
        mult = {}
        for k, v in (seas_d.get("mult") or {}).items():
            try:
                mult[int(k)] = float(v)
            except Exception:
                continue
        seas = DOWSeasonalityModel(mult=mult)
    else:
        seas = DOWSeasonalityModel(mult={})

    return PricingWorldModel(demand=demand, conversion=conv, seasonality=seas)
