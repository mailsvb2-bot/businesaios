from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True


@dataclass(frozen=True)
class LegacyExperimentResult:
    """Historical winner/confidence projection.

    The canonical ExperimentResult owner is core.experiments.types.
    This shape remains only for backward-compatible callers that still consume
    the old summary projection.
    """

    experiment_id: str = ""
    winner: str = ""
    confidence: float = 0.0


ExperimentResult = LegacyExperimentResult

__all__ = ["CANON_COMPAT_SHIM", "ExperimentResult", "LegacyExperimentResult"]
