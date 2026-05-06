from __future__ import annotations

FORBIDDEN_SUFFIXES = ("brain", "autopilot", "governor")


def is_safe_module_name(name: str) -> bool:
    return not any(name.endswith(suffix) for suffix in FORBIDDEN_SUFFIXES)

__all__ = [
    "FORBIDDEN_SUFFIXES",
    "is_safe_module_name",
]
