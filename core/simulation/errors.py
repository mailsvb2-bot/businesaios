from __future__ import annotations


class SimulationError(Exception):
    pass


class SimulationGuardViolation(SimulationError):
    pass
