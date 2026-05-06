from __future__ import annotations

import os
from pathlib import Path


def ensure_writable_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o777)
    except OSError:
        pass
    return path


def prepare_writable_file(path: Path) -> Path:
    ensure_writable_dir(path.parent)
    if path.exists():
        try:
            os.chmod(path, 0o666)
        except OSError:
            pass
    return path


def safe_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> Path:
    path = prepare_writable_file(path)
    path.write_text(text, encoding=encoding)
    try:
        os.chmod(path, 0o666)
    except OSError:
        pass
    return path


def safe_write_bytes(path: Path, data: bytes) -> Path:
    path = prepare_writable_file(path)
    path.write_bytes(data)
    try:
        os.chmod(path, 0o666)
    except OSError:
        pass
    return path
