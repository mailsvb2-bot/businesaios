import os
from pathlib import Path

CONFIG_DIRS = ["config", "core/config", "runtime/config"]
ROOT = Path(__file__).resolve().parents[2]

def test_single_config_root():
    existing = [d for d in CONFIG_DIRS if os.path.exists(d)]
    assert len(existing) <= 3

def test_canonical_config_owners_exist():
    assert (ROOT / "products").exists()
    assert (ROOT / "core/config").exists()
    assert (ROOT / "runtime/config").exists()
    assert (ROOT / "runtime/platform/config").exists()
