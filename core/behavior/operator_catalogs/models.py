from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from config.final_hidden_logic_policy import DEFAULT_OPERATOR_CATALOG_POLICY


def _clamp(x: float, lo: float, hi: float) -> float:
    x = float(x)
    if x < lo:
        return float(lo)
    if x > hi:
        return float(hi)
    return x


@dataclass(frozen=True)
class OperatorCatalog:
    """Operator Catalog (Behavioral OS).

    This is the behavioral equivalent of OfferCatalog:
    - closed alphabet stays in code (dirac_operators)
    - coefficients live in catalogs (YAML), tenant/product scoped

    Catalog only *scales* / *tunes* bounded operators; it must never
    introduce new operator keys.
    """

    catalog_id: str

    # Global phase gain for diagonal impulses (kept small by design)
    phase_gain: float = DEFAULT_OPERATOR_CATALOG_POLICY.default_phase_gain

    # Ring coupling coefficients (bounded)
    k_tp: float = DEFAULT_OPERATOR_CATALOG_POLICY.default_k_tp
    k_vp: float = DEFAULT_OPERATOR_CATALOG_POLICY.default_k_vp
    k_it: float = DEFAULT_OPERATOR_CATALOG_POLICY.default_k_it

    # Anti drain coefficient (bounded)
    anti_drain: float = DEFAULT_OPERATOR_CATALOG_POLICY.default_anti_drain

    # Optional event-specific scaling: normalized event_type -> multiplier
    event_scales: Mapping[str, float] = field(default_factory=dict)

    # Optional per-domain multiplier (domain -> multiplier)
    domain_scales: Mapping[str, float] = field(default_factory=dict)

    # Optional per-channel multiplier (compat surface; does not introduce new logic)
    channel_scales: Mapping[str, float] = field(default_factory=dict)

    def validate(self) -> None:
        cid = str(self.catalog_id or "").strip()
        if not cid:
            raise ValueError("OperatorCatalog.catalog_id is required")
        object.__setattr__(self, "catalog_id", cid)

        # Hard safety bounds: catalogs can tune but not break invariants.
        object.__setattr__(self, "phase_gain", _clamp(self.phase_gain, DEFAULT_OPERATOR_CATALOG_POLICY.phase_gain_min, DEFAULT_OPERATOR_CATALOG_POLICY.phase_gain_max))
        object.__setattr__(self, "k_tp", _clamp(self.k_tp, DEFAULT_OPERATOR_CATALOG_POLICY.coupling_min, DEFAULT_OPERATOR_CATALOG_POLICY.coupling_max))
        object.__setattr__(self, "k_vp", _clamp(self.k_vp, DEFAULT_OPERATOR_CATALOG_POLICY.coupling_min, DEFAULT_OPERATOR_CATALOG_POLICY.coupling_max))
        object.__setattr__(self, "k_it", _clamp(self.k_it, DEFAULT_OPERATOR_CATALOG_POLICY.coupling_min, DEFAULT_OPERATOR_CATALOG_POLICY.coupling_max))
        object.__setattr__(self, "anti_drain", _clamp(self.anti_drain, DEFAULT_OPERATOR_CATALOG_POLICY.anti_drain_min, DEFAULT_OPERATOR_CATALOG_POLICY.anti_drain_max))

        # Clean mapping keys
        es: dict[str, float] = {}
        for k, v in dict(self.event_scales or {}).items():
            kk = str(k or "").strip().lower()
            if not kk:
                continue
            es[kk] = float(_clamp(float(v), DEFAULT_OPERATOR_CATALOG_POLICY.scale_min, DEFAULT_OPERATOR_CATALOG_POLICY.scale_max))
        object.__setattr__(self, "event_scales", es)

        ds: dict[str, float] = {}
        for k, v in dict(self.domain_scales or {}).items():
            kk = str(k or "").strip().lower()
            if not kk:
                continue
            ds[kk] = float(_clamp(float(v), DEFAULT_OPERATOR_CATALOG_POLICY.scale_min, DEFAULT_OPERATOR_CATALOG_POLICY.scale_max))
        object.__setattr__(self, "domain_scales", ds)

        cs: dict[str, float] = {}
        for k, v in dict(self.channel_scales or {}).items():
            kk = str(k or "").strip().lower()
            if not kk:
                continue
            cs[kk] = float(_clamp(float(v), DEFAULT_OPERATOR_CATALOG_POLICY.scale_min, DEFAULT_OPERATOR_CATALOG_POLICY.scale_max))
        object.__setattr__(self, "channel_scales", cs)

    def scale_for(self, *, event_type: str, domain: str | None = None) -> float:
        et = str(event_type or "").strip().lower()
        dom = str(domain or "").strip().lower()
        s1 = float(self.event_scales.get(et, DEFAULT_OPERATOR_CATALOG_POLICY.default_scale))
        s2 = float(self.domain_scales.get(dom, DEFAULT_OPERATOR_CATALOG_POLICY.default_scale)) if dom else DEFAULT_OPERATOR_CATALOG_POLICY.default_scale
        return float(s1 * s2)


def catalog_from_raw(raw: Mapping[str, Any]) -> OperatorCatalog:
    d = dict(raw or {})
    cat = OperatorCatalog(
        catalog_id=str(d.get("catalog_id") or "").strip(),
        phase_gain=float(d.get("phase_gain", DEFAULT_OPERATOR_CATALOG_POLICY.default_phase_gain)),
        k_tp=float(d.get("k_tp", DEFAULT_OPERATOR_CATALOG_POLICY.default_k_tp)),
        k_vp=float(d.get("k_vp", DEFAULT_OPERATOR_CATALOG_POLICY.default_k_vp)),
        k_it=float(d.get("k_it", DEFAULT_OPERATOR_CATALOG_POLICY.default_k_it)),
        anti_drain=float(d.get("anti_drain", DEFAULT_OPERATOR_CATALOG_POLICY.default_anti_drain)),
        event_scales=(d.get("event_scales") if isinstance(d.get("event_scales"), dict) else {}) or {},
        domain_scales=(d.get("domain_scales") if isinstance(d.get("domain_scales"), dict) else {}) or {},
        channel_scales=(d.get("channel_scales") if isinstance(d.get("channel_scales"), dict) else {}) or {},
    )
    # validate (and normalize)
    cat.validate()
    return cat
