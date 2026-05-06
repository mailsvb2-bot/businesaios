from __future__ import annotations

AXIS_INTENT = 0
AXIS_TRUST = 1
AXIS_VALUE = 2
AXIS_PAYMENT = 3

DIRAC_BEHAVIOR_AXES: tuple[str, str, str, str] = (
    "intent",
    "trust",
    "value",
    "payment",
)
