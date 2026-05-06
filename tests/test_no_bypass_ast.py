from pathlib import Path

from runtime.security.ast_bypass_guard import scan_repo


def test_no_decision_bypass_ast():
    scan_repo(Path(__file__).resolve().parents[1])
