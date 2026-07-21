from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from application.admin.platform_control_center.risk_projection_layer import (
    RiskProjectionLayer,
    _is_compat_surface_name,
    _is_suspicious_surface_name,
    _iter_mapping_rows,
    _mapping_rows,
    _name_tokens,
    _require_non_negative_int,
    _require_positive_int,
    _require_text,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_contract_helpers_are_exact_and_surface_tokens_are_not_substrings() -> None:
    assert _require_text("x", " value ") == "value"
    for value in (None, 1, " "):
        with pytest.raises(ValueError):
            _require_text("x", value)

    assert _require_non_negative_int("x", 0) == 0
    assert _require_positive_int("x", 2) == 2
    for value in (True, 1.0, "1", -1):
        with pytest.raises(ValueError):
            _require_non_negative_int("x", value)
    with pytest.raises(ValueError):
        _require_positive_int("x", 0)

    assert _mapping_rows("rows", ({"x": 1},)) == ({"x": 1},)
    assert tuple(_iter_mapping_rows("rows", ({"x": 1},))) == ({"x": 1},)
    for value in ("x", b"x", bytearray(b"x"), {"x": 1}, None, [1]):
        with pytest.raises(ValueError):
            _mapping_rows("rows", cast(object, value))

    def late_invalid():
        yield {"x": 1}
        yield 2

    iterator = _iter_mapping_rows("rows", cast(object, late_invalid()))
    assert next(iterator) == {"x": 1}
    with pytest.raises(ValueError):
        next(iterator)

    assert _name_tokens("legacy-public_api.py") == {"legacy", "public", "api"}
    assert _is_suspicious_surface_name("legacy_adapter.py") is True
    assert _is_suspicious_surface_name("public_api.py") is True
    assert _is_compat_surface_name("public_api.py") is False
    assert _is_compat_surface_name("legacy_adapter.py") is True
    assert _is_suspicious_surface_name("incompatible.py") is False


def test_root_validation_and_safe_block_scanning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="path"):
        RiskProjectionLayer(cast(Path, object()))
    with pytest.raises(ValueError, match="exist"):
        RiskProjectionLayer(tmp_path / "missing")
    file_root = _write(tmp_path / "file.txt", "x")
    with pytest.raises(ValueError, match="directory"):
        RiskProjectionLayer(file_root)

    root = tmp_path / "repo"
    root.mkdir()
    _write(root / "alpha" / "small.py", "x = 1\n\n")
    _write(root / "alpha" / "legacy_adapter.py", "x = 1\n")
    _write(root / "alpha" / "public_api.py", "x = 1\n")
    _write(root / "alpha" / "large.py", "\n".join("x = 1" for _ in range(450)))
    _write(root / "beta" / "empty.txt", "not python")
    _write(root / ".hidden" / "hidden.py", "x = 1")
    _write(root / "alpha" / ".cache" / "hidden.py", "x = 1")
    _write(root / "alpha" / "node_modules" / "hidden.py", "x = 1")
    (root / "plain.txt").write_text("x")

    outside = tmp_path / "outside"
    outside.mkdir()
    _write(outside / "escape.py", "x = 1")
    try:
        (root / "linked").symlink_to(outside, target_is_directory=True)
        (root / "alpha" / "linked.py").symlink_to(outside / "escape.py")
    except OSError:
        pass

    broken = root / "alpha" / "broken.py"
    broken.write_bytes(b"\xff")
    layer = RiskProjectionLayer(str(root))
    rows, files = layer.build_block_rows()
    assert [row["block"] for row in rows] == ["alpha"]
    row = rows[0]
    assert row["python_files"] == 5
    assert row["python_lines"] == 453
    assert row["public_api_files"] == 1
    assert row["compat_files"] == 1
    assert row["large_files"] == 1
    assert row["risk_score"] == 4
    assert row["maturity"] == "watch"
    assert {item["path"] for item in files} == {
        "alpha/broken.py",
        "alpha/large.py",
        "alpha/legacy_adapter.py",
        "alpha/public_api.py",
        "alpha/small.py",
    }

    _write(root / "gamma" / "legacy_one.py", "x=1")
    _write(root / "gamma" / "compat_two.py", "x=1")
    _write(root / "gamma" / "shim_three.py", "x=1")
    rows2, _ = layer.build_block_rows()
    gamma = next(item for item in rows2 if item["block"] == "gamma")
    assert gamma["risk_score"] == 6 and gamma["maturity"] == "needs_work"

    real_rglob = Path.rglob
    monkeypatch.setattr(
        Path,
        "rglob",
        lambda self, pattern: (_ for _ in ()).throw(OSError("scan down"))
        if self.name == "alpha"
        else real_rglob(self, pattern),
    )
    with pytest.raises(RuntimeError, match="failed to scan block"):
        layer._python_files(root / "alpha")
    monkeypatch.undo()

    real_iterdir = Path.iterdir
    monkeypatch.setattr(
        Path,
        "iterdir",
        lambda self: (_ for _ in ()).throw(OSError("down")) if self == root.resolve() else real_iterdir(self),
    )
    with pytest.raises(RuntimeError, match="list repository"):
        tuple(layer._top_level_blocks())


def test_recommendations_are_validated_deduped_ranked_and_bounded(tmp_path: Path) -> None:
    layer = RiskProjectionLayer(tmp_path)
    files = [
        {"path": "a/god.py", "name": "god.py", "lines": 700},
        {"path": "a/large.py", "name": "large.py", "lines": 450},
        {"path": "a/legacy_wrapper.py", "name": "legacy_wrapper.py", "lines": 10},
        {"path": "a/incompatible.py", "name": "incompatible.py", "lines": 10},
        {"path": "a/god.py", "name": "god.py", "lines": 700},
    ]
    blocks = [
        {"block": "a", "compat_files": 8, "public_api_files": 3},
        {"block": "public", "compat_files": 0, "public_api_files": 3},
        {"block": "clean", "compat_files": 0, "public_api_files": 0},
    ]
    risks = layer.build_risk_recommendations(block_rows=blocks, python_files=files)
    assert [(risk.severity, risk.risk_type) for risk in risks] == [
        ("critical", "god_module_pressure"),
        ("major", "legacy_pressure"),
        ("major", "large_module"),
        ("minor", "public_api_spread"),
        ("minor", "surface_spread"),
        ("minor", "public_api_spread"),
    ]
    assert len(risks) == 6
    assert any(risk.file_path == "public/" and risk.risk_type == "public_api_spread" for risk in risks)

    many = [{"path": f"a/{index}.py", "name": "legacy.py", "lines": 0} for index in range(100)]
    assert len(layer.build_risk_recommendations(block_rows=[], python_files=many)) == 40

    invalid_files = [
        [{"path": "a.py", "name": "a.py", "lines": True}],
        [{"path": "", "name": "a.py", "lines": 1}],
        [{"path": "a.py", "name": "", "lines": 1}],
    ]
    for value in invalid_files:
        with pytest.raises(ValueError):
            layer.build_risk_recommendations(block_rows=[], python_files=value)
    for value in (
        [{"block": "", "compat_files": 0, "public_api_files": 0}],
        [{"block": "a", "compat_files": "8"}],
        [{"block": "a", "public_api_files": True}],
    ):
        with pytest.raises(ValueError):
            layer.build_risk_recommendations(block_rows=value, python_files=[])


def test_dependency_scan_is_safe_deterministic_and_ignores_invalid_or_relative_imports(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _write(root / "a" / "__init__.py", "import b\nimport b.sub\nfrom c.mod import x\nfrom .local import y\n")
    _write(root / "a" / "public_api.py", "import b\nimport a.local\n")
    _write(root / "a" / "bad.py", "this is not python !!!")
    _write(root / "a" / "encoding.py", "x=1")
    (root / "a" / "encoding.py").write_bytes(b"\xff")
    _write(root / "b" / "__init__.py", "from a import x\n")
    _write(root / "c" / "__init__.py", "x=1\n")
    _write(root / "excluded" / "notpy.txt", "")
    layer = RiskProjectionLayer(root)
    rows = layer.build_dependency_rows()
    assert rows == [
        {
            "source_block": "a",
            "target_block": "b",
            "import_count": 2,
            "edge_kind": "cross_block_import",
            "graph_mode": "representative_scan",
        },
        {
            "source_block": "a",
            "target_block": "c",
            "import_count": 1,
            "edge_kind": "cross_block_import",
            "graph_mode": "representative_scan",
        },
        {
            "source_block": "b",
            "target_block": "a",
            "import_count": 1,
            "edge_kind": "cross_block_import",
            "graph_mode": "representative_scan",
        },
    ]


def test_conflict_rows_fail_closed_and_preserve_single_owner_evidence(tmp_path: Path) -> None:
    layer = RiskProjectionLayer(tmp_path)
    blocks = [
        {"block": "a", "compat_files": 8},
        {"block": "b", "compat_files": 8},
        {"block": "c", "compat_files": 8},
        {"block": "d", "compat_files": 0},
    ]
    deps = [
        {"source_block": "a", "target_block": "b", "import_count": 2},
        {"source_block": "b", "target_block": "a", "import_count": 3},
        {"source_block": "a", "target_block": "c", "import_count": 1},
        {"source_block": "a", "target_block": "d", "import_count": 1},
    ]
    rows = layer.build_conflict_rows(block_rows=blocks, dependency_rows=deps)
    assert len(rows) == 2
    assert rows[0]["conflict_kind"] == "bidirectional_dependency" and rows[0]["score"] == 5
    assert rows[1]["conflict_kind"] == "legacy_overlap" and rows[1]["score"] == 1

    assert len(layer.build_conflict_rows(block_rows=blocks, dependency_rows=deps + [deps[0]])) == 2
    invalid = [
        ([{"block": "a"}, {"block": "a", "compat_files": 1}], []),
        ([], [{"source_block": "a", "target_block": "a", "import_count": 1}]),
        ([], [{"source_block": "", "target_block": "b", "import_count": 1}]),
        ([], [{"source_block": "a", "target_block": "b", "import_count": 0}]),
        (
            [],
            [
                {"source_block": "a", "target_block": "b", "import_count": 1},
                {"source_block": "a", "target_block": "b", "import_count": 2},
            ],
        ),
    ]
    for block_rows, dependency_rows in invalid:
        with pytest.raises(ValueError):
            layer.build_conflict_rows(block_rows=block_rows, dependency_rows=dependency_rows)


def test_visual_map_validates_dedupes_and_caps_rows(tmp_path: Path) -> None:
    layer = RiskProjectionLayer(tmp_path)
    row = {
        "source_block": "b",
        "target_block": "a",
        "conflict_kind": "legacy_overlap",
        "score": 2,
        "summary": "x",
    }
    result = layer.build_visual_conflict_map(
        conflict_rows=[
            row,
            row,
            {"source_block": "c", "target_block": "a", "conflict_kind": "bidirectional_dependency"},
        ]
    )
    assert result["nodes"] == [
        {"id": "a", "label": "a"},
        {"id": "b", "label": "b"},
        {"id": "c", "label": "c"},
    ]
    assert len(result["edges"]) == 2
    assert result["edges"][0]["weight"] == 2
    assert result["edges"][1]["weight"] == 1
    assert result["render_mode"] == "force_graph"

    many = [
        {"source_block": f"s{index}", "target_block": f"t{index}", "conflict_kind": "legacy_overlap", "score": 1}
        for index in range(100)
    ]
    assert len(layer.build_visual_conflict_map(conflict_rows=many)["edges"]) == 80

    def bounded_rows():
        yield from many[:80]
        raise AssertionError("row 81 must not be consumed")

    assert len(layer.build_visual_conflict_map(conflict_rows=bounded_rows())["edges"]) == 80
    for invalid in (
        [{"source_block": "a", "target_block": "a", "conflict_kind": "x", "score": 1}],
        [{"source_block": "", "target_block": "b", "conflict_kind": "x", "score": 1}],
        [{"source_block": "a", "target_block": "b", "conflict_kind": "", "score": 1}],
        [{"source_block": "a", "target_block": "b", "conflict_kind": "x", "score": True}],
    ):
        with pytest.raises(ValueError):
            layer.build_visual_conflict_map(conflict_rows=invalid)
