import pathlib


def test_distributed_imports_only_canonical_envelope():
    repo = pathlib.Path(__file__).resolve().parents[1]

    for py in repo.rglob("distributed*.py"):
        rel = py.relative_to(repo).as_posix()
        if rel.startswith("runtime/platform/support/"):
            continue
        text = py.read_text(encoding="utf-8")
        assert "core.decision.envelope" not in text
        assert "core.ai.decision" in text
