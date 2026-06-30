from __future__ import annotations

from dataclasses import dataclass
from runtime.learning_loop import LearningLoopService

CANON_THIN_HANDLER = True

@dataclass(slots=True)
class LearningLoopRunHandler:
    service: LearningLoopService

    def handle(self, *, policy_id: str, subject_id: str) -> dict[str, object]:
        return self.service.run(policy_id=policy_id, subject_id=subject_id)
