from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from canon.collapse.architecture_lock_tests import run_legacy_architecture_locks
from canon.collapse.data_flow_validator import scan_shadow_state, verify_single_state_source_files_exist
from canon.collapse.decision_path_map import LegacyCanonConfig, build_default_config
from canon.collapse.duplicate_detector import DuplicateCluster, scan_duplicate_logic
from canon.collapse.god_module_detector import GodModuleFinding, scan_god_modules
from canon.collapse.hidden_logic_detector import HiddenLogicFinding, scan_hidden_logic
from canon.collapse.legacy_wrapper_guard import WrapperViolation, scan_legacy_wrappers


@dataclass(frozen=True)
class LegacyCleanupFindings:
    duplicate_logic: tuple[DuplicateCluster, ...]
    shadow_state: tuple
    hidden_logic: tuple[HiddenLogicFinding, ...]
    god_modules: tuple[GodModuleFinding, ...]
    legacy_wrappers: tuple[WrapperViolation, ...]
    missing_state_surfaces: tuple

    @property
    def total_findings(self) -> int:
        return len(self.duplicate_logic) + len(self.shadow_state) + len(self.hidden_logic) + len(self.god_modules) + len(self.legacy_wrappers) + len(self.missing_state_surfaces)


@dataclass(frozen=True)
class LegacyCleanupResult:
    config: LegacyCanonConfig
    findings: LegacyCleanupFindings
    critical_messages: tuple[str, ...]
    major_messages: tuple[str, ...]
    minor_messages: tuple[str, ...]

    @property
    def is_clean(self) -> bool:
        return self.findings.total_findings == 0

    def as_dict(self) -> dict[str, object]:
        return {"repo_root": str(self.config.repo_root), "is_clean": self.is_clean, "total_findings": self.findings.total_findings, "critical_messages": list(self.critical_messages), "major_messages": list(self.major_messages), "minor_messages": list(self.minor_messages)}


class LegacyCleanupEngine:
    def __init__(self, config: LegacyCanonConfig) -> None:
        self._config = config

    def run(self) -> LegacyCleanupResult:
        findings = LegacyCleanupFindings(
            duplicate_logic=scan_duplicate_logic(self._config), shadow_state=scan_shadow_state(self._config),
            hidden_logic=scan_hidden_logic(self._config), god_modules=scan_god_modules(self._config),
            legacy_wrappers=scan_legacy_wrappers(self._config), missing_state_surfaces=verify_single_state_source_files_exist(self._config),
        )
        report = run_legacy_architecture_locks(self._config.repo_root)
        return LegacyCleanupResult(self._config, findings, report.critical_messages, report.major_messages, report.minor_messages)


def run_legacy_cleanup(repo_root: Path) -> LegacyCleanupResult:
    return LegacyCleanupEngine(build_default_config(repo_root)).run()


__all__ = ["LegacyCleanupFindings", "LegacyCleanupResult", "LegacyCleanupEngine", "run_legacy_cleanup"]
