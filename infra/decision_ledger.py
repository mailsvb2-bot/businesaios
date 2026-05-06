from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DecisionLedgerEntry:
    entry_id: str
    decision_name: str
    actor: str
    status: str
    policy_version_id: str | None = None
    approval_request_id: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class DecisionLedger:
    _entries: list[DecisionLedgerEntry] = field(default_factory=list)

    def append(self, entry: DecisionLedgerEntry) -> None:
        self._entries.append(entry)

    def entries(self) -> tuple[DecisionLedgerEntry, ...]:
        return tuple(self._entries)
