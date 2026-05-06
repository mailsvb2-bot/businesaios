from pathlib import Path


def test_headless_runtime_paths_have_single_owner() -> None:
    text = Path('execution/headless_paths.py').read_text(encoding='utf-8')
    assert 'CANON_HEADLESS_RUNTIME_PATHS = True' in text
    assert 'CANON_HEADLESS_RUNTIME_PATHS_SINGLE_OWNER = True' in text
    assert 'def build_headless_runtime_paths(' in text


def test_headless_boot_and_governance_use_shared_paths_owner() -> None:
    boot = Path('execution/headless_boot.py').read_text(encoding='utf-8')
    governance = Path('execution/governance_service.py').read_text(encoding='utf-8')
    assert 'build_headless_runtime_paths' in boot
    assert 'build_headless_runtime_paths' in governance
    assert 'Path(".runtime") / "headless_ledger"' not in boot
    assert "Path('.runtime') / 'headless_baseline_history'" not in governance
