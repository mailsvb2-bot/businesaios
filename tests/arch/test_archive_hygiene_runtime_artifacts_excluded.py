from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_runtime_artifact_junk_is_not_checked_in() -> None:
    forbidden = [
        ROOT / ".runtime",
        ROOT / ".pytest_cache",
        ROOT / "runtime/data/demo/.runtime",
    ]
    for path in forbidden:
        assert not path.exists(), f"unexpected runtime artifact directory present: {path.relative_to(ROOT)}"


def test_root_level_wave_reports_are_not_checked_in() -> None:
    forbidden = tuple(ROOT.glob('wave*_*.txt'))
    assert not forbidden, f"unexpected wave report artifacts present: {[path.name for path in forbidden]}"


def test_runtime_platform_marker_file_is_retired() -> None:
    assert not (ROOT / 'runtime.platform').exists(), 'unexpected runtime.platform marker file present'
    assert (ROOT / 'runtime' / 'platform').is_dir(), 'runtime/platform directory missing'
