from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


FILES = [
    ROOT / "runtime/platform/config/feature_flags.py",
    ROOT / "runtime/evolution/worker.py",
    ROOT / "runtime/evolution/main.py",
    ROOT / "runtime/boot/tenant_hard_gate.py",
    ROOT / "interfaces/messaging/_shared/mode_reader.py",
]


def test_selected_files_use_canonical_env_access() -> None:
    for path in FILES:
        text = path.read_text(encoding="utf-8")
        assert "os.getenv(" not in text, f"raw os.getenv still present in {path.relative_to(ROOT)}"


def test_platform_env_flags_module_exists() -> None:
    path = ROOT / "runtime/platform/config/env_flags.py"
    text = path.read_text(encoding="utf-8")
    assert "from runtime.boot.env import env_bool, env_float, env_int, env_str" in text
    assert "def env_path(" in text
