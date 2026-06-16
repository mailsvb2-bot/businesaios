from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

CANON_HEADLESS_RUNTIME_PATHS = True
CANON_HEADLESS_RUNTIME_PATHS_SINGLE_OWNER = True

_TRUE_VALUES = {"1", "true", "yes", "on"}


def _env(name: str) -> str:
    return str(os.getenv(name, "")).strip()


def _is_test_process() -> bool:
    return _env("BUSINESAIOS_TEST_RUN").lower() in _TRUE_VALUES or bool(_env("PYTEST_CURRENT_TEST"))


def _resolve_headless_root(*, root_dir: str | Path | None = None) -> Path:
    if root_dir is not None:
        return Path(root_dir)
    env_root = _env("BUSINESAIOS_HEADLESS_ROOT")
    if env_root:
        return Path(env_root)
    if _is_test_process():
        return Path(".runtime")
    env_data = _env("BUSINESAIOS_DATA_DIR")
    if env_data:
        return Path(env_data)
    return Path(".runtime")


@dataclass(frozen=True)
class HeadlessRuntimePaths:
    root_dir: Path

    @property
    def headless_ledger_dir(self) -> Path:
        return self.root_dir / "headless_ledger"

    @property
    def business_operating_memory_dir(self) -> Path:
        return self.root_dir / "business_operating_memory"

    @property
    def headless_state_dir(self) -> Path:
        return self.root_dir / "headless_state"

    @property
    def headless_effects_dir(self) -> Path:
        return self.root_dir / "headless_effects"

    @property
    def headless_idempotency_dir(self) -> Path:
        return self.root_dir / "headless_idempotency"

    @property
    def headless_operator_handoff_dir(self) -> Path:
        return self.root_dir / "headless_operator_handoff"

    @property
    def business_memory_dir(self) -> Path:
        return self.root_dir / "business_memory"

    @property
    def autonomy_counters_dir(self) -> Path:
        return self.root_dir / "autonomy_counters"

    @property
    def autonomy_kill_switch_dir(self) -> Path:
        return self.root_dir / "autonomy_kill_switch"

    @property
    def adaptive_optimization_dir(self) -> Path:
        return self.root_dir / "adaptive_optimization"

    @property
    def owner_path_dir(self) -> Path:
        return self.root_dir / "owner_path"

    @property
    def strategy_memory_dir(self) -> Path:
        return self.root_dir / "strategy_memory"

    @property
    def performance_learning_dir(self) -> Path:
        return self.root_dir / "performance_learning"

    @property
    def multi_goal_planner_dir(self) -> Path:
        return self.root_dir / "multi_goal_planner"

    @property
    def retry_learning_dir(self) -> Path:
        return self.root_dir / "retry_learning"

    @property
    def headless_baseline_history_dir(self) -> Path:
        return self.root_dir / "headless_baseline_history"

    @property
    def headless_baselines_dir(self) -> Path:
        return self.root_dir / "headless_baselines"

    @property
    def headless_baseline_rollbacks_dir(self) -> Path:
        return self.root_dir / "headless_baseline_rollbacks"

    @property
    def scenario_baseline_catalog_dir(self) -> Path:
        return self.root_dir / "scenario_baseline_catalog"


def build_headless_runtime_paths(*, root_dir: str | Path | None = None) -> HeadlessRuntimePaths:
    return HeadlessRuntimePaths(root_dir=_resolve_headless_root(root_dir=root_dir))


__all__ = [
    "CANON_HEADLESS_RUNTIME_PATHS",
    "CANON_HEADLESS_RUNTIME_PATHS_SINGLE_OWNER",
    "HeadlessRuntimePaths",
    "build_headless_runtime_paths",
]
