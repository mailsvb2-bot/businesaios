from __future__ import annotations

from pathlib import Path


def test_make_ci_shell_targets_do_not_require_executable_mode() -> None:
    root = Path(__file__).resolve().parents[2]
    makefile = (root / "Makefile").read_text(encoding="utf-8")

    required = (
        "ci-guard:\n\tbash ./ci/check_prod_strict.sh",
        "then bash ./ci/check_prod_strict.sh prod.env; fi",
        "then bash ./ci/check_prod_strict.sh .env.prod; fi",
        "ci-locks:\n\tbash ./ci/check_locks.sh",
        "locks:\n\tbash ./ci/check_locks.sh",
    )
    missing = [snippet for snippet in required if snippet not in makefile]

    assert not missing, (
        "Make CI shell targets must invoke scripts through bash so a checkout "
        f"with non-executable script modes remains runnable; missing={missing}"
    )
