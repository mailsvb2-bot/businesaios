from __future__ import annotations


def growth_step(users: float, acquisition: float, conversion: float, retention: float) -> float:
    """Simple growth loop:
      U_{t+1} = U_t + A_t*c - U_t*(1-r)
    """
    u = float(users)
    a = float(acquisition)
    c = max(0.0, min(1.0, float(conversion)))
    r = max(0.0, min(1.0, float(retention)))
    churn = u * (1.0 - r)
    return max(0.0, u + a * c - churn)


def feedback_step(value: float, *, gain: float, damping: float, input_signal: float = 0.0) -> float:
    """Stable feedback primitive:
      x_{t+1} = x_t + gain*(input - x_t) - damping*x_t
    """
    x = float(value)
    g = float(gain)
    d = float(damping)
    inp = float(input_signal)
    return x + g * (inp - x) - d * x
