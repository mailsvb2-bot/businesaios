from __future__ import annotations

from scripts.ci.bundle_makefile_block import CI_MAKEFILE_BLOCK
from scripts.ci.canon_bundle_io import append_makefile_block_once, ensure_pytest_ini, write


def finalize_bundle() -> None:
    ensure_pytest_ini()
    append_makefile_block_once(CI_MAKEFILE_BLOCK)
    write("Makefile.ci.fragment", CI_MAKEFILE_BLOCK)
    print("Canonical CI/CD V7 project bundle prepared successfully.")
