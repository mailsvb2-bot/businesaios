from __future__ import annotations


class LearningLoopError(Exception):
    pass


class LearningLoopGuardViolation(LearningLoopError):
    pass
