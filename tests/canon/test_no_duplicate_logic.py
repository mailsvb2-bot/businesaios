from __future__ import annotations

from pathlib import Path

from canon.legacy.architecture_lock_tests import build_lock_config
from canon.legacy.duplicate_detector import scan_duplicate_logic
from canon.legacy.god_module_detector import scan_god_modules

ROOT = Path(__file__).resolve().parents[2]


def test_no_critical_duplicate_logic_clusters() -> None:
    config = build_lock_config(ROOT)
    clusters = scan_duplicate_logic(config)
    critical = [item for item in clusters if item.severity.value == "critical"]
    assert critical == [], (
        "Critical semantic duplicate logic clusters detected across decision/governance surfaces:\n"
        + "\n".join(
            "- "
            + f"{cluster.kind}:{cluster.name} [{cluster.reason}] "
            + ", ".join(f"{fragment.relpath}:{fragment.lineno}" for fragment in cluster.fragments)
            for cluster in critical[:25]
        )
    )


def test_no_critical_god_modules_in_decision_surfaces() -> None:
    config = build_lock_config(ROOT)
    findings = scan_god_modules(config)
    critical = [item for item in findings if item.severity.value == "critical"]
    assert critical == [], (
        "Critical god modules detected in non-allowlisted surfaces:\n"
        + "\n".join(
            f"- {item.relpath} lines={item.lines} functions={item.functions} classes={item.classes} imports={item.imports} reasons={','.join(item.reasons)}"
            for item in critical[:25]
        )
    )
