from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from config.yaml_loader_shared import YamlLoadResult
from config.yaml_loader_shared import load_yaml as _shared_load_yaml
from config.yaml_loader_shared import load_yaml_optional as _shared_load_yaml_optional


def _read(value: str | Path) -> str:
    if isinstance(value, Path):
        return value.read_text(encoding="utf-8")
    text = str(value)
    p = Path(text)
    if "\n" not in text and len(text) < 4096 and p.exists():
        return p.read_text(encoding="utf-8")
    return text


def load_yaml(value: str | Path) -> dict[str, Any]:
    data = _shared_load_yaml(_read(value))
    if data is None:
        return {}
    if not isinstance(data, Mapping):
        raise ValueError("canonical yaml config must be a mapping")
    return dict(data)


def load_yaml_optional(value: str | Path | None) -> dict[str, Any]:
    if value is None:
        return {}
    data = _shared_load_yaml_optional(_read(value))
    if data is None:
        return {}
    if not isinstance(data, Mapping):
        raise ValueError("canonical yaml config must be a mapping")
    return dict(data)


__all__ = ["YamlLoadResult", "load_yaml", "load_yaml_optional"]
