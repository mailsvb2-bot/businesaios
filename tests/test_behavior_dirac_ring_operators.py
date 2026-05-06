from __future__ import annotations

import math

from core.behavior.complex4 import Complex4
from core.behavior.dirac_operators import apply_event_operator, required_operator_keys
from core.behavior.impulse_contract import impulse_for_event
from core.retention.event_types import KNOWN_EVENT_TYPES


def test_impulse_contract_covers_known_event_types() -> None:
    required = set(required_operator_keys())
    known = set(KNOWN_EVENT_TYPES)
    missing = sorted(list(known - required))
    assert missing == [], f"Operator layer missing known types: {missing}"


def test_impulses_are_bounded_and_deterministic() -> None:
    for et in sorted(list(KNOWN_EVENT_TYPES)):
        event = {"event_type": et, "payload": {}, "timestamp_ms": 1}
        a = impulse_for_event(event)
        b = impulse_for_event(event)
        assert a == b
        dI, dT, dV, dP, dA = a
        assert abs(dI) <= 0.25 + 1e-9
        assert abs(dT) <= 0.25 + 1e-9
        assert abs(dV) <= 0.25 + 1e-9
        assert abs(dP) <= 0.25 + 1e-9
        assert abs(dA) <= 0.40 + 1e-9


def test_operator_step_is_stable_and_renormalized() -> None:
    psi = Complex4.zeros().renormalize(1.0)
    anti = 0.0
    for et in sorted(list(KNOWN_EVENT_TYPES)):
        event = {"event_type": et, "payload": {}, "timestamp_ms": 1}
        r = apply_event_operator(psi=psi, anti=anti, event=event, context={})
        assert 0.0 <= r.anti <= 1.0
        n2 = r.psi.norm2()
        assert math.isfinite(n2)
        assert abs(n2 - 1.0) <= 1e-6
        psi, anti = r.psi, r.anti
