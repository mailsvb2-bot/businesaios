from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_architecture_canon_doc_exists():
    assert (ROOT / "docs/ARCHITECTURE_CANON_V20.md").exists()
