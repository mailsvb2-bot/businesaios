from __future__ import annotations

from core.behavior.operators.operator_application import apply_operator
from core.behavior.math.complex4 import Complex4


def simulate_operator_sequence(
    psi_re: tuple[float, float, float, float],
    psi_im: tuple[float, float, float, float],
    operator_keys: list[str],
) -> dict[str, object]:
    psi = Complex4(psi_re, psi_im)
    for operator_key in operator_keys:
        psi = apply_operator(psi, operator_key)
    return {
        "psi_re": psi.re,
        "psi_im": psi.im,
        "amplitude": psi.magnitude(),
        "phase": psi.phase(),
        "norm_sq": psi.norm_sq(),
    }
