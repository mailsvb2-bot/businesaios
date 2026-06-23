from __future__ import annotations

from typing import Any

CANON_RUNTIME_BOOT_PHASES_OBSERVABILITY_SHIM = True


def emit_boot_diagnostic_lines(*, observability: Any | None = None, phase: str = "runtime_boot", lines: tuple[str, ...] = ()) -> tuple[str, ...]:
    diagnostics = tuple(str(line) for line in lines if str(line).strip())
    recorder = getattr(observability, "record_decision_trace", None)
    if callable(recorder):
        for line in diagnostics:
            recorder(trace_name="runtime_boot", stage=str(phase), diagnostic=line)
    return diagnostics


__all__ = ["CANON_RUNTIME_BOOT_PHASES_OBSERVABILITY_SHIM", "emit_boot_diagnostic_lines"]
