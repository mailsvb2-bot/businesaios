import os
import runpy
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import pytest


def _is_ci() -> bool:
    if os.getenv("BUSINESAIOS_CERT_STRICT", "").strip() in {"1", "true", "TRUE", "yes", "YES"}:
        return True
    if os.getenv("CI", "").strip() in {"1", "true", "TRUE", "yes", "YES"}:
        return True
    if os.getenv("GITHUB_ACTIONS", "").strip() in {"1", "true", "TRUE"}:
        return True
    return False


@pytest.mark.gate
def test_repo_certification_strict_in_ci() -> None:
    """Enforce strict certification in CI only.

    Locally this test is skipped by default to keep the dev loop fast and friendly.
    """

    if not _is_ci():
        pytest.skip("Strict certification is enforced only in CI (set BUSINESAIOS_CERT_STRICT=1 to enable locally).")

    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "certify_repo.py"
    assert script.exists(), "certify_repo.py must exist"

    env_before = dict(os.environ)
    argv_before = list(sys.argv)
    try:
        os.environ["BUSINESAIOS_CERT_STRICT"] = "1"
        sys.argv = [str(script), "--root", str(repo_root)]
        buf = StringIO()
        with redirect_stdout(buf):
            runpy.run_path(str(script), run_name="__main__")
    except SystemExit as e:
        code = int(getattr(e, "code", 1) or 0)
        out = buf.getvalue() if "buf" in locals() else ""
        if code != 0:
            raise AssertionError("Repo certification failed in strict mode.\n" + (out or "<empty>"))
    finally:
        os.environ.clear()
        os.environ.update(env_before)
        sys.argv = argv_before
