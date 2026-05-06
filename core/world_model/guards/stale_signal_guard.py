from __future__ import annotations

from core.world_model.enums import SignalFreshness
from core.world_model.errors import StaleSignalError
from core.world_model.types import FreshnessReport


class StaleSignalGuard:
    def __init__(self, *, strict_readers: tuple[str, ...] = ("customer", "product", "market")) -> None:
        self._strict_readers = tuple(strict_readers)

    def validate(self, *, freshness: FreshnessReport) -> None:
        for reader_name in self._strict_readers:
            status = freshness.per_reader.get(reader_name)
            if status in {SignalFreshness.STALE, SignalFreshness.MISSING}:
                raise StaleSignalError(f"world_model stale_or_missing reader={reader_name} status={status}")
