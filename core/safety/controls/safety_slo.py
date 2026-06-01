from __future__ import annotations

from dataclasses import dataclass

CANON_SAFETY_SLO = True


@dataclass(frozen=True)
class SafetySLO:
    max_intervention_rate: float = 0.30
    max_failure_rate: float = 0.10


DEFAULT_SAFETY_SLO = SafetySLO()


__all__ = ['CANON_SAFETY_SLO', 'DEFAULT_SAFETY_SLO', 'SafetySLO']
