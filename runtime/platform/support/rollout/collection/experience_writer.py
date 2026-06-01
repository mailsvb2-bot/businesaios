from __future__ import annotations


class ExperienceWriter:
    def write(self, replay_buffer, transitions) -> None:
        for transition in transitions:
            replay_buffer.add(transition)

__all__ = [
    "ExperienceWriter",
]
