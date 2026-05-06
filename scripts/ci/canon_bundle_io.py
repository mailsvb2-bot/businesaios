"""IO helpers for canon CI bundle apply scripts."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def write(rel: str, content: str, root: Path | None = None) -> None:
    r = root or repo_root()
    path = r / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip("\n"), encoding="utf-8")


def append_makefile_block_once(block: str, root: Path | None = None) -> None:
    r = root or repo_root()
    path = r / "Makefile"
    if not path.exists():
        raise FileNotFoundError(f"Makefile not found: {path}")

    content = path.read_text(encoding="utf-8")
    marker = "python scripts/ci/cli.py --gate fast"
    if marker in content:
        print("Makefile already contains canonical CI/CD targets.")
        return

    updated = content.rstrip() + "\n\n" + dedent(block).strip() + "\n"
    path.write_text(updated, encoding="utf-8")
    print("Makefile patched with canonical CI/CD targets.")


def ensure_pytest_ini(root: Path | None = None) -> None:
    r = root or repo_root()
    path = r / "pytest.ini"

    required_markers = [
        "asyncio: async test marker (no pytest-asyncio dependency; tests should be hermetic)",
        "gate: CI-only certification / release gate",
        "lock: Contract/architecture lock tests (must never be skipped in CI)",
        "slow: Long running tests",
        "integration: marks integration tests that exercise cross-module or external contours",
        "arch: marks architecture tests that protect dependency and layering rules",
    ]
    required_addopts_parts = ["--strict-markers", "--strict-config"]

    if not path.exists():
        content = dedent("""
            [pytest]
            minversion = 7.0
            addopts =
              -p no:cacheprovider
              -p no:ddtrace
              -q
              --strict-markers
              --strict-config
              -ra
            testpaths =
              tests
            python_files =
              test_*.py
            python_classes =
              Test*
            python_functions =
              test_*
            markers =
              asyncio: async test marker (no pytest-asyncio dependency; tests should be hermetic)
              gate: CI-only certification / release gate
              lock: Contract/architecture lock tests (must never be skipped in CI)
              slow: Long running tests
              integration: marks integration tests that exercise cross-module or external contours
              arch: marks architecture tests that protect dependency and layering rules
        """).lstrip("\n")
        path.write_text(content, encoding="utf-8")
        print("pytest.ini created with canonical marker discipline.")
        return

    text = path.read_text(encoding="utf-8")
    updated = text

    if "[pytest]" not in updated:
        updated = "[pytest]\n" + updated.lstrip()

    if "addopts" not in updated:
        updated = updated.rstrip() + "\naddopts = --strict-markers --strict-config\n"
    else:
        lines = updated.splitlines()
        patched: list[str] = []
        changed_addopts = False
        for line in lines:
            if line.strip().startswith("addopts"):
                current = line.split("=", 1)[1].strip() if "=" in line else ""
                for part in required_addopts_parts:
                    if part not in current:
                        current = (current + " " + part).strip()
                patched.append(f"addopts = {current}")
                changed_addopts = True
            else:
                patched.append(line)
        if changed_addopts:
            updated = "\n".join(patched) + ("\n" if text.endswith("\n") else "")

    if "markers =" not in updated:
        updated = updated.rstrip() + "\nmarkers =\n"
        for marker in required_markers:
            updated += f"  {marker}\n"
    else:
        lines = updated.splitlines()
        existing_markers: list[str] = []
        in_markers = False
        for line in lines:
            if line.strip().startswith("markers"):
                in_markers = True
                continue
            if in_markers:
                if line.startswith(" ") or line.startswith("\t"):
                    existing_markers.append(line.strip())
                elif line.strip():
                    break

        missing = [m for m in required_markers if m not in existing_markers]
        if missing:
            patched_lines: list[str] = []
            inserted = False
            i = 0
            while i < len(lines):
                line = lines[i]
                patched_lines.append(line)
                if line.strip().startswith("markers"):
                    i += 1
                    while i < len(lines):
                        next_line = lines[i]
                        if next_line.startswith(" ") or next_line.startswith("\t") or not next_line.strip():
                            patched_lines.append(next_line)
                            i += 1
                        else:
                            break
                    for marker in missing:
                        patched_lines.append(f"  {marker}")
                    inserted = True
                    continue
                i += 1
            if inserted:
                updated = "\n".join(patched_lines) + ("\n" if text.endswith("\n") else "\n")

    if updated != text:
        path.write_text(updated, encoding="utf-8")
        print("pytest.ini updated with canonical marker discipline.")
    else:
        print("pytest.ini already satisfies canonical marker discipline.")


__all__ = ["write", "append_makefile_block_once", "ensure_pytest_ini", "repo_root"]
