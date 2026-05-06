"""Canonical reporting requirements for deep project audits.

This module is intentionally small and stable because many architecture
checks import it during test collection.  The requirements enumerate the
minimum verification sections that any deep repair / audit report must
cover.
"""

from __future__ import annotations

REPORT_REQUIREMENTS = (
    "functional capability report",
    "critical error inventory",
    "world-model canonical path verification",
    "world-model pinning verification",
    "world-model replay and audit verification",
    "single DecisionCore verification",
    "single execution contract verification",
    "single dataflow verification",
    "infrastructure ownership verification",
    "anti-second-brain verification",
    "boot wiring integrity verification",
    "thin handlers integrity verification",
    "observability coverage verification",
    "clean archive verification",
)


def required_report_sections() -> tuple[str, ...]:
    """Return the canonical report section names.

    Tuple return keeps the surface immutable for callers that want a stable,
    hashable package-level contract.
    """

    return REPORT_REQUIREMENTS
