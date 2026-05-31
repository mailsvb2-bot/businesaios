"""Canonical YAML loader.

CANON_COMPAT_SHIM = True

Accepts either:
- a filesystem path
- raw YAML text

This keeps a single loading contract while remaining compatible with legacy
call sites that still pass `path.read_text(...)`. PyYAML is intentionally lazy:
module import must not fail just because optional runtime dependencies are not
installed yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class YamlLoadResult:
    path: str
    data: dict[str, Any]


_CACHE: dict[str, dict[str, Any]] = {}


def _safe_load_yaml(raw_text: str) -> Any:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise RuntimeError("PyYAML is required to parse YAML. Install project requirements first.") from exc
    return yaml.safe_load(raw_text)


def _looks_like_yaml_text(value: str) -> bool:
    s = str(value or "")
    return ("\n" in s) or (":" in s and ("/" not in s and "\\" not in s))


def _parse_yaml_text(raw_text: str, *, allow_empty: bool) -> dict[str, Any]:
    raw = _safe_load_yaml(raw_text)
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("YAML root must be a mapping")
    if (not allow_empty) and (not raw):
        raise ValueError("YAML document is empty")
    return dict(raw)


def load_yaml(source: str | Path, *, allow_empty: bool = True, cache: bool = True) -> dict[str, Any]:
    if isinstance(source, Path):
        p = source.expanduser().resolve()
        key = str(p)
        if cache and key in _CACHE:
            return dict(_CACHE[key])
        if not p.exists():
            raise FileNotFoundError(str(p))
        data = _parse_yaml_text(p.read_text(encoding="utf-8"), allow_empty=allow_empty)
        if cache:
            _CACHE[key] = dict(data)
        return data

    text = str(source or "")
    candidate = Path(text).expanduser()
    if not _looks_like_yaml_text(text):
        try:
            candidate = candidate.resolve()
            if candidate.exists():
                return load_yaml(candidate, allow_empty=allow_empty, cache=cache)
        except OSError:
            pass
    return _parse_yaml_text(text, allow_empty=allow_empty)


def load_yaml_optional(path: Path, *, default: dict[str, Any] | None = None, cache: bool = True) -> dict[str, Any]:
    p = path.expanduser().resolve()
    if not p.exists():
        return dict(default or {})
    return load_yaml(p, cache=cache)
