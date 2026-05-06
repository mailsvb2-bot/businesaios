from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OperatorSessionRecord:
    session_id: str
    actor: str
    actor_scope: str
    metadata: dict = field(default_factory=dict)


@dataclass
class OperatorSessionRegistry:
    _sessions: dict[str, OperatorSessionRecord] = field(default_factory=dict)

    def register(self, record: OperatorSessionRecord) -> None:
        self._sessions[record.session_id] = record

    def get(self, session_id: str) -> OperatorSessionRecord:
        return self._sessions[session_id]

    def list_sessions(self) -> tuple[OperatorSessionRecord, ...]:
        return tuple(self._sessions.values())
