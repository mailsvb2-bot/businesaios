from __future__ import annotations

from .hard_case_mining import hard_case_mining

class CurriculumManager:
    def level_for_epoch(self, epoch: int) -> int:
        return max(0, epoch)

class CurriculumPolicy:
    def difficulty(self, epoch: int) -> int:
        return epoch

class OpponentSampler:
    def sample(self, opponents):
        if not opponents:
            raise ValueError("opponents must not be empty")
        return opponents[0]

class SelfPlayManager:
    def next_pair(self, players):
        if len(players) < 2:
            raise ValueError("Need at least two players")
        return players[0], players[1]

class TeacherForcing:
    def apply(self, predicted, target, ratio: float = 1.0):
        return target if ratio >= 1.0 else predicted

_ALIAS_EXPORTS = {
    "curriculum_manager": "CurriculumManager",
    "curriculum_policy": "CurriculumPolicy",
    "opponent_sampler": "OpponentSampler",
    "self_play_manager": "SelfPlayManager",
    "teacher_forcing": "TeacherForcing",
}

__all__ = [
    "CurriculumManager",
    "CurriculumPolicy",
    "hard_case_mining",
    "OpponentSampler",
    "SelfPlayManager",
    "TeacherForcing",
]
