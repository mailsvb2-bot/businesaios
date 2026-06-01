from pathlib import Path

ALLOWED_IMPORT_PREFIXES = (
    "core.",
    "kernel.",
    "application.",
    "ports.",
    "canon.",
    "runtime.",
    "adapters.",
    "runtime.platform.",
    "api.",
    "tests.",
    "contracts.",
    "config.",
    "governance.",
    "survival.",
)


def test_no_unexpected_dotted_imports_in_core():
    root = Path(__file__).resolve().parents[2]
    core = root / "core"
    if not core.exists():
        return
    bad = []
    for py in core.rglob("*.py"):
        txt = py.read_text(encoding="utf-8", errors="ignore")
        for line in txt.splitlines():
            s = line.strip()
            if s.startswith("from "):
                pkg = s.split()[1]
                if pkg.startswith("."):
                    continue
                if "." in pkg and not pkg.startswith(ALLOWED_IMPORT_PREFIXES):
                    if pkg.split(".")[0] in {"typing", "dataclasses", "contextvars", "pathlib", "json", "time", "concurrent", "collections", "observability"}:
                        continue
                    bad.append(f"{py.relative_to(root)}: {s}")
    assert not bad, "Unexpected imports in core:\n" + "\n".join(bad)
