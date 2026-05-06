from __future__ import annotations


class WorldModelError(Exception):
    pass


class WorldModelGuardError(WorldModelError):
    pass


class StaleSignalError(WorldModelGuardError):
    pass


class IncompleteStateError(WorldModelGuardError):
    pass


class WorldModelIntegrityError(WorldModelGuardError):
    pass


class WorldModelGuardViolation(WorldModelGuardError):
    pass
