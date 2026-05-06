from __future__ import annotations

import os
from pathlib import Path


CANON_SAFETY_RUNTIME_PATHS = True


def safety_runtime_data_dir() -> Path:
    raw = os.getenv('BUSINESAIOS_SAFETY_DATA_DIR', 'data/runtime/safety')
    base = Path(str(raw or 'data/runtime/safety')).expanduser()
    if not base.is_absolute():
        base = (Path.cwd() / base).resolve()
    else:
        base = base.resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base


def safety_sqlite_path(name: str) -> str:
    return str(safety_runtime_data_dir() / f'{name}.sqlite3')


def safety_jsonl_path(name: str) -> str:
    return str(safety_runtime_data_dir() / f'{name}.jsonl')


__all__ = ['CANON_SAFETY_RUNTIME_PATHS', 'safety_jsonl_path', 'safety_runtime_data_dir', 'safety_sqlite_path']
