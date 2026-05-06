from __future__ import annotations

FORBIDDEN_RUNTIME_RAW_ACCESS_PATTERNS: tuple[str, ...] = (
    "registry.get(",
    "runtime.get(",
)
