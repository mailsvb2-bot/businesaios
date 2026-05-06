from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from canon.legacy.data_flow_validator import scan_shadow_state, verify_single_state_source_files_exist
from canon.legacy.decision_path_map import FindingSeverity, LegacyCanonConfig, build_default_config
from canon.legacy.duplicate_detector import scan_duplicate_logic
from canon.legacy.god_module_detector import scan_god_modules
from canon.legacy.hidden_logic_detector import scan_hidden_logic
from canon.legacy.legacy_wrapper_guard import scan_legacy_wrappers


@dataclass(frozen=True)
class LegacyLockReport:
    critical_messages: tuple[str, ...]
    major_messages: tuple[str, ...]
    minor_messages: tuple[str, ...]

    @property
    def is_clean(self) -> bool:
        return not self.critical_messages and not self.major_messages and not self.minor_messages

    @property
    def has_critical_failures(self) -> bool:
        return bool(self.critical_messages)


def build_lock_config(repo_root: Path) -> LegacyCanonConfig:
    return build_default_config(repo_root)


def run_legacy_architecture_locks(repo_root: Path) -> LegacyLockReport:
    config = build_lock_config(repo_root)

    duplicate_logic = scan_duplicate_logic(config)
    wrappers = scan_legacy_wrappers(config)
    hidden_logic = scan_hidden_logic(config)
    shadow_state = scan_shadow_state(config)
    god_modules = scan_god_modules(config)
    missing_state_surfaces = verify_single_state_source_files_exist(config)

    critical: list[str] = []
    major: list[str] = []
    minor: list[str] = []

    def _push(severity: FindingSeverity, message: str) -> None:
        if severity == FindingSeverity.CRITICAL:
            critical.append(message)
        elif severity == FindingSeverity.MAJOR:
            major.append(message)
        else:
            minor.append(message)

    for item in duplicate_logic:
        _push(
            item.severity,
            f"duplicate_logic:{item.kind}:{item.name}: {item.reason}: "
            + ", ".join(f"{frag.relpath}:{frag.lineno}" for frag in item.fragments),
        )
    for item in wrappers:
        _push(item.severity, f"wrapper:{item.relpath}:{item.lineno}:{item.symbol}: {item.reason}")
    for item in hidden_logic:
        _push(item.severity, f"hidden_logic:{item.relpath}:{item.lineno}:{item.symbol}: {item.reason}")
    for item in shadow_state:
        _push(item.severity, f"shadow_state:{item.relpath}:{item.lineno}:{item.symbol}: {item.reason}")
    for item in god_modules:
        _push(
            item.severity,
            f"god_module:{item.relpath}: lines={item.lines} functions={item.functions} classes={item.classes} imports={item.imports} reasons={','.join(item.reasons)}",
        )
    for item in missing_state_surfaces:
        _push(item.severity, f"state_surface:{item.relpath}: {item.reason}")

    return LegacyLockReport(
        critical_messages=tuple(critical),
        major_messages=tuple(major),
        minor_messages=tuple(minor),
    )


def assert_no_critical_legacy_findings(repo_root: Path) -> None:
    report = run_legacy_architecture_locks(repo_root)
    if report.has_critical_failures:
        raise AssertionError("Critical legacy-collapse violations detected:\n" + "\n".join(report.critical_messages))


__all__ = [
    "LegacyLockReport",
    "build_lock_config",
    "run_legacy_architecture_locks",
    "assert_no_critical_legacy_findings",
]
