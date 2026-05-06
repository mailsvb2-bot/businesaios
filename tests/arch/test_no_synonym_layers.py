import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_no_user_users_split():
    assert not (os.path.exists("core/user") and os.path.exists("core/users")), \
        "user/users namespace split forbidden"

def test_no_runtime_boot_shadow_pipeline():
    assert not (ROOT / "runtime/boot/_boot_phases.py").exists()

def test_user_namespace_collapsed():
    assert (ROOT / "core/users/read_model.py").exists()
    assert not (ROOT / "core/user/read_model.py").exists()
