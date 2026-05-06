from __future__ import annotations

from pathlib import Path

import pytest

from runtime.platform.config.yaml_loader import load_yaml


def test_load_yaml_reads_mapping(tmp_path: Path) -> None:
    p = tmp_path / "a.yaml"
    p.write_text("a: 1\nb: two\n", encoding="utf-8")
    d = load_yaml(p)
    assert d["a"] == 1
    assert d["b"] == "two"


def test_load_yaml_rejects_non_mapping(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_yaml(p)
