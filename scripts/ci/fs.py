from __future__ import annotations

import os
from pathlib import Path
from contextlib import suppress


def ensure_writable_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    with suppress(OSError):
        os.chmod(path, 0o777)
    return path


def prepare_writable_file(path: Path) -> Path:
    ensure_writable_dir(path.parent)
    if path.exists():
        with suppress(OSError):
            os.chmod(path, 0o666)
    return path


def safe_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> Path:
    path = prepare_writable_file(path)
    path.write_text(text, encoding=encoding)
    with suppress(OSError):
        os.chmod(path, 0o666)
    return path


def safe_write_bytes(path: Path, data: bytes) -> Path:
    path = prepare_writable_file(path)
    path.write_bytes(data)
    with suppress(OSError):
        os.chmod(path, 0o666)
    return path
