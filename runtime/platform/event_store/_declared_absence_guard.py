from __future__ import annotations

"""Helpers for explicit import-stable modules that are intentionally not bundled."""

from typing import Any

CANON_DECLARED_ABSENCE = True


def exported_names(*names: str) -> list[str]:
    base = ["CANON_DECLARED_ABSENCE", "build_declared_absence_metadata", "declared_absence_runtime_error"]
    return base + [name for name in names if name]


def build_declared_absence_metadata(*, module: str, canonical_module: str, reason: str) -> dict[str, Any]:
    return {
        "declared_absence": True,
        "placeholder": True,
        "module": str(module),
        "canonical_module": str(canonical_module),
        "reason": str(reason),
    }


def declared_absence_runtime_error(*, module: str, canonical_module: str, reason: str) -> RuntimeError:
    return RuntimeError(
        f"{module} is not bundled in this archive. Canonical module: {canonical_module}. Reason: {reason}"
    )


__all__ = [
    "CANON_DECLARED_ABSENCE",
    "exported_names",
    "build_declared_absence_metadata",
    "declared_absence_runtime_error",
]
