from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Final


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


CANONICAL_DECISION_CORE_IMPORT_PATH: Final[str] = "core.ai.decision_core.DecisionCore"
CANONICAL_DECISION_CORE_MODULE: Final[str] = "core.ai.decision_core"
CANONICAL_DECISION_CORE_PUBLIC_MODULE: Final[str] = "core.decision_core"
COMPAT_DECISION_ENGINE_MODULE: Final[str] = "core.application.decision_service.DecisionService"
CANONICAL_DECISION_PATH_SERVICES: Final[tuple[str, ...]] = ("decision_core", "governance_chain", "action_executor")
CANONICAL_STATE_FILES: Final[tuple[str, ...]] = ("application/world_state/world_state_assembler.py", "runtime/world_state/public_api.py", "bootstrap/world_model_contract.py")
SCAN_INCLUDE_PREFIXES: Final[tuple[str, ...]] = ("core/", "runtime/", "governance/", "canon/")
EXCLUDED_PREFIXES: Final[tuple[str, ...]] = (".git/", ".github/", ".venv/", "venv/", "__pycache__/", "artifacts/", ".runtime/", "assets/", "app/web/", "canon/collapse/")
FORBIDDEN_DECISION_CLASS_NAMES: Final[tuple[str, ...]] = ("StrategyBrain", "GrowthBrain", "AutonomousBrain", "SecondDecisionCore", "DecisionEngineFacade", "PolicyBrain", "ExecutionBrain", "ShadowDecisionCore")
FORBIDDEN_DECISION_METHOD_NAMES: Final[tuple[str, ...]] = ("decide_strategy", "issue_strategy", "emit_final_action", "select_final_action", "issue_final_action", "execute_final_action")
FORBIDDEN_SHADOW_STATE_NAMES: Final[tuple[str, ...]] = ("shadow_state", "shadow_world_model", "parallel_world_model", "duplicate_state", "secondary_world_state", "second_world_state", "mirror_world_state")
DECISION_SURFACE_PREFIXES: Final[tuple[str, ...]] = ("core/ai/", "core/application/", "core/governance/", "runtime/execution/", "runtime/boot/", "runtime/decision_input/", "governance/")
THIN_WRAPPER_HINTS: Final[tuple[str, ...]] = ("public_api", "compat", "wrapper", "facade", "alias", "bridge")
ALLOWED_THIN_WRAPPER_CALLS: Final[tuple[str, ...]] = ("install_public_api_alias", "install_alias")
DUPLICATE_LOGIC_NAME_HINTS: Final[tuple[str, ...]] = ("decision", "router", "governance", "policy", "budget", "executor", "action", "state", "world", "strategy")
MAX_THIN_WRAPPER_NON_EMPTY_LINES: Final[int] = 40
MAX_THIN_WRAPPER_FUNCTION_BODY_STATEMENTS: Final[int] = 3
GOD_MODULE_LINES_MAJOR: Final[int] = 700
GOD_MODULE_LINES_CRITICAL: Final[int] = 1000
GOD_MODULE_FUNCTIONS_MAJOR: Final[int] = 30
GOD_MODULE_FUNCTIONS_CRITICAL: Final[int] = 45
GOD_MODULE_CLASSES_MAJOR: Final[int] = 10
GOD_MODULE_CLASSES_CRITICAL: Final[int] = 16
GOD_MODULE_IMPORTS_MAJOR: Final[int] = 35
GOD_MODULE_IMPORTS_CRITICAL: Final[int] = 60
GOD_MODULE_ALLOWLIST_PREFIXES: Final[tuple[str, ...]] = ("contracts/", "tests/")
HIDDEN_LOGIC_ACTION_KEYS: Final[tuple[str, ...]] = ("selected_action", "final_action", "action_type", "best_action", "issued_action")
HIDDEN_LOGIC_RETURN_HINTS: Final[tuple[str, ...]] = ("decide", "select", "choose", "rank", "optimize", "issue")


@dataclass(frozen=True)
class LegacyCanonConfig:
    repo_root: Path
    include_prefixes: tuple[str, ...] = SCAN_INCLUDE_PREFIXES
    excluded_prefixes: tuple[str, ...] = EXCLUDED_PREFIXES
    decision_surface_prefixes: tuple[str, ...] = DECISION_SURFACE_PREFIXES
    canonical_state_files: tuple[str, ...] = CANONICAL_STATE_FILES
    forbidden_decision_class_names: tuple[str, ...] = FORBIDDEN_DECISION_CLASS_NAMES
    forbidden_decision_method_names: tuple[str, ...] = FORBIDDEN_DECISION_METHOD_NAMES
    forbidden_shadow_state_names: tuple[str, ...] = FORBIDDEN_SHADOW_STATE_NAMES
    thin_wrapper_hints: tuple[str, ...] = THIN_WRAPPER_HINTS
    allowed_thin_wrapper_calls: tuple[str, ...] = ALLOWED_THIN_WRAPPER_CALLS
    duplicate_logic_name_hints: tuple[str, ...] = DUPLICATE_LOGIC_NAME_HINTS
    max_thin_wrapper_non_empty_lines: int = MAX_THIN_WRAPPER_NON_EMPTY_LINES
    max_thin_wrapper_function_body_statements: int = MAX_THIN_WRAPPER_FUNCTION_BODY_STATEMENTS
    god_module_lines_major: int = GOD_MODULE_LINES_MAJOR
    god_module_lines_critical: int = GOD_MODULE_LINES_CRITICAL
    god_module_functions_major: int = GOD_MODULE_FUNCTIONS_MAJOR
    god_module_functions_critical: int = GOD_MODULE_FUNCTIONS_CRITICAL
    god_module_classes_major: int = GOD_MODULE_CLASSES_MAJOR
    god_module_classes_critical: int = GOD_MODULE_CLASSES_CRITICAL
    god_module_imports_major: int = GOD_MODULE_IMPORTS_MAJOR
    god_module_imports_critical: int = GOD_MODULE_IMPORTS_CRITICAL
    god_module_allowlist_prefixes: tuple[str, ...] = GOD_MODULE_ALLOWLIST_PREFIXES
    hidden_logic_action_keys: tuple[str, ...] = HIDDEN_LOGIC_ACTION_KEYS
    hidden_logic_return_hints: tuple[str, ...] = HIDDEN_LOGIC_RETURN_HINTS
    compatibility_modules: tuple[str, ...] = field(default_factory=lambda: (CANONICAL_DECISION_CORE_MODULE, CANONICAL_DECISION_CORE_PUBLIC_MODULE, COMPAT_DECISION_ENGINE_MODULE))

    def normalize_relpath(self, path: Path) -> str:
        return path.relative_to(self.repo_root).as_posix()

    def is_excluded_relpath(self, relpath: str) -> bool:
        return relpath.replace("\\", "/").startswith(self.excluded_prefixes)

    def is_included_relpath(self, relpath: str) -> bool:
        normalized = relpath.replace("\\", "/")
        return normalized.startswith(self.include_prefixes) and not self.is_excluded_relpath(normalized)

    def is_decision_surface(self, relpath: str) -> bool:
        return relpath.replace("\\", "/").startswith(self.decision_surface_prefixes)

    def is_god_module_allowlisted(self, relpath: str) -> bool:
        return relpath.replace("\\", "/").startswith(self.god_module_allowlist_prefixes)

    def canonical_state_paths(self) -> tuple[Path, ...]:
        return tuple(self.repo_root / item for item in self.canonical_state_files)


def build_default_config(repo_root: Path) -> LegacyCanonConfig:
    return LegacyCanonConfig(repo_root=repo_root)


__all__ = ["FindingSeverity", "CANONICAL_DECISION_CORE_IMPORT_PATH", "CANONICAL_DECISION_CORE_MODULE", "CANONICAL_DECISION_CORE_PUBLIC_MODULE", "COMPAT_DECISION_ENGINE_MODULE", "CANONICAL_DECISION_PATH_SERVICES", "CANONICAL_STATE_FILES", "LegacyCanonConfig", "build_default_config"]
