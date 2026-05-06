from pathlib import Path


def test_main_uses_runtime_boot_env_helpers():
    text = Path("main.py").read_text(encoding="utf-8")
    assert "os.getenv(" not in text
    assert "from runtime.boot.env import env_bool, env_guard_production_mode, env_str" in text
