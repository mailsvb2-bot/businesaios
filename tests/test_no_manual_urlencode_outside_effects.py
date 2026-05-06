from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EFFECTS_IMPL = (REPO_ROOT / "runtime" / "_internal" / "_effects_impl.py").resolve()
HTTP_CLIENT = (REPO_ROOT / "runtime" / "_internal" / "effects_clients" / "http_client.py").resolve()
HTTP_TRANSPORT = (REPO_ROOT / "runtime" / "_internal" / "http_transport.py").resolve()


def _iter_py_files():
    for p in REPO_ROOT.rglob("*.py"):
        if any(part in (".venv", "venv", "__pycache__") for part in p.parts):
            continue
        # This rule is about production code; tests may mention urlencode in assertions.
        if "tests" in p.parts:
            continue
        yield p


def test_urlencode_used_only_inside_effects_impl():
    offenders: list[str] = []
    for p in _iter_py_files():
        text = p.read_text(encoding="utf-8")
        if "urlencode(" in text:
            if p.resolve() not in {EFFECTS_IMPL, HTTP_CLIENT, HTTP_TRANSPORT}:
                offenders.append(str(p.relative_to(REPO_ROOT)))

    assert offenders == [], (
        "urlencode() must not be used outside sealed effects transport:\n"
        "  - runtime/_internal/_effects_impl.py\n"
        "  - runtime/_internal/effects_clients/http_client.py\n"
        f"Offenders: {offenders}"
    )
