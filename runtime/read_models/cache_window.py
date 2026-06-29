"""Read-model cache window controller.

Avoids "God code" where arbitrary modules mutate os.environ directly.
This module is the single point that adjusts READ_MODEL_CACHE_WINDOW_S.

The runtime uses environment variables as configuration source, so we keep the
implementation minimal and reversible.
"""

from __future__ import annotations

import os

from runtime.platform.config.env_flags import env_float


def set_cache_window_seconds(value_s: float) -> None:
    try:
        v = float(value_s)
    except Exception:
        return
    v = max(0.0, min(60.0, v))
    os.environ["READ_MODEL_CACHE_WINDOW_S"] = str(v)


def get_cache_window_seconds(default_s: float = 2.0) -> float:
    try:
        return float(env_float("READ_MODEL_CACHE_WINDOW_S", float(default_s), lo=0.0, hi=60.0))
    except Exception:
        return float(default_s)
