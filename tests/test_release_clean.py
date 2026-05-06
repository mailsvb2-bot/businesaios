from pathlib import Path

FORBIDDEN_EXT = {".pyc", ".db", ".bak", ".bak2", ".tmp"}
FORBIDDEN_DIRS = {"__pycache__", ".pytest_cache"}


def test_repo_has_no_runtime_artifacts():
    root = Path(__file__).resolve().parents[1]

    bad = []
    for p in root.rglob("*"):
        if p.suffix in FORBIDDEN_EXT or p.name in FORBIDDEN_DIRS:
            bad.append(str(p))

    assert not bad, "Forbidden artifacts found:\n" + "\n".join(bad)


def test_deployment_contract_is_shipped() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "docs" / "DEPLOYMENT_CONTRACT.md").exists()


def test_repo_has_no_empty_non_init_files() -> None:
    root = Path(__file__).resolve().parents[1]
    bad = []
    for p in root.rglob("*"):
        if p.is_file() and p.stat().st_size == 0 and p.name != "__init__.py":
            bad.append(str(p))
    assert not bad, "Unexpected empty non-init files found:\n" + "\n".join(bad)
