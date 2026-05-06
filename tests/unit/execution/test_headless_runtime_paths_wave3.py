from pathlib import Path

from execution.headless_paths import build_headless_runtime_paths


def test_build_headless_runtime_paths_defaults_to_runtime_root() -> None:
    paths = build_headless_runtime_paths()
    assert paths.root_dir == Path('.runtime')
    assert paths.headless_ledger_dir == Path('.runtime') / 'headless_ledger'
    assert paths.scenario_baseline_catalog_dir == Path('.runtime') / 'scenario_baseline_catalog'


def test_build_headless_runtime_paths_accepts_explicit_root() -> None:
    paths = build_headless_runtime_paths(root_dir='/tmp/businesaios-headless')
    assert paths.root_dir == Path('/tmp/businesaios-headless')
    assert paths.business_operating_memory_dir == Path('/tmp/businesaios-headless') / 'business_operating_memory'
