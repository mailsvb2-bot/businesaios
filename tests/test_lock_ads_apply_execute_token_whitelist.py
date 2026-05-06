from __future__ import annotations

from pathlib import Path

TOKEN = "ads_apply_execute@v1"

ROOT = Path(__file__).resolve().parents[1]

ALLOWED = {
    "core/policies/telegram/handlers/ads_apply_flow.py",
    "runtime/boot/actions_catalog.py",
    "runtime/handlers/ads_apply_execute.py",
    "tests/test_lock_ads_apply_single_path.py",
    "tests/test_lock_ads_apply_execute_token_whitelist.py",
}

def test_no_new_files_contain_ads_apply_execute_token() -> None:
    hits: list[str] = []
    for p in ROOT.rglob('*'):
        if not p.is_file():
            continue
        if p.suffix not in {'.py', '.md', '.txt', '.yml', '.yaml', '.json', '.sh'}:
            continue
        rel = p.relative_to(ROOT).as_posix()
        txt = p.read_text(encoding='utf-8', errors='ignore')
        if TOKEN in txt and rel not in ALLOWED:
            hits.append(rel)
    assert hits == [], f'Unexpected TOKEN occurrences outside whitelist: {hits}'
