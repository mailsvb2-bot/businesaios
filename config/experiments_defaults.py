from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class ExperimentDefaults:
    metric_minimum_detectable_effect: float = 0.0
    variant_metric_value: float = 0.0


DEFAULT_EXPERIMENT_DEFAULTS = ExperimentDefaults()


__all__ = ["ExperimentDefaults", "DEFAULT_EXPERIMENT_DEFAULTS"]
