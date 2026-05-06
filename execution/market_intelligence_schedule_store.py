from __future__ import annotations

from pathlib import Path
import os
from threading import RLock
from typing import Any

from governance.persistence_codec import atomic_write_json, read_json_or_default


CANON_MARKET_INTELLIGENCE_SCHEDULE_STORE = True


def _text(value: object, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _store_path() -> Path:
    explicit = _text(os.getenv("BUSINESAIOS_MARKET_INTELLIGENCE_SCHEDULE_STORE_PATH"))
    if explicit:
        return Path(explicit)
    data_dir = _text(os.getenv("DATA_DIR"), default=".runtime_data")
    return Path(data_dir) / "market_intelligence" / "schedule_state.json"


class PersistentMarketIntelligenceScheduleStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else _store_path()
        self._lock = RLock()
        self._state: dict[str, Any] = {"last_run_at": {}}
        self._load()

    def load_last_run_at(self) -> dict[str, str]:
        return {str(k): str(v) for k, v in dict(self._state.get("last_run_at", {})).items()}

    def save_last_run_at(self, state: dict[str, str]) -> None:
        with self._lock:
            self._state["last_run_at"] = {str(k): str(v) for k, v in dict(state).items()}
            self._flush()

    def _load(self) -> None:
        raw = read_json_or_default(self._path, default=self._state)
        if isinstance(raw, dict):
            self._state = {"last_run_at": dict(raw.get("last_run_at", {}))}

    def _flush(self) -> None:
        atomic_write_json(self._path, self._state)


__all__ = [
    "CANON_MARKET_INTELLIGENCE_SCHEDULE_STORE",
    "PersistentMarketIntelligenceScheduleStore",
]
