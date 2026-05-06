from __future__ import annotations

class ModelUpdateScheduler:
    def should_run(self, row_count: int) -> bool:
        return int(row_count) >= 20
