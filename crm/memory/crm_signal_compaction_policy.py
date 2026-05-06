from __future__ import annotations


class CrmSignalCompactionPolicy:
    def compact(self, signals: list[dict[str, object]], *, max_items: int = 20) -> list[dict[str, object]]:
        return list(signals)[-max_items:]
