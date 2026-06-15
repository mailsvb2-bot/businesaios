from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


ACTIVE_FILES = [
    ROOT / "runtime/platform/config/feature_flags.py",
    ROOT / "runtime/evolution/worker.py",
    ROOT / "runtime/evolution/main.py",
    ROOT / "interfaces/messaging/_shared/mode_reader.py",
]

RETIRED_FILES = [
    ROOT / "runtime/boot/tenant_hard_gate.py",
]


def test_selected_files_use_canonical_env_access() -> None:
    for path in ACTIVE_FILES:
        assert path.exists(), f"env access lock target is missing: {path.relative_to(ROOT)}"
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT)
        assert "os.getenv(" not in text, f"raw os.getenv still present in {rel}"


def test_retired_env_access_targets_stay_retired() -> None:
    for path in RETIRED_FILES:
        assert not path.exists(), f"retired env access target unexpectedly returned: {path.relative_to(ROOT)}"


def test_platform_env_flags_module_exists() -> None:
    path = ROOT / "runtime/platform/config/env_flags.py"
    text = path.read_text(encoding="utf-8")
    assert "from runtime.boot.env import env_bool, env_float, env_int, env_str" in text
    assert "def env_path(" in text
