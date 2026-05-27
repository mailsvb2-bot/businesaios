from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EFFECTS_IMPL = REPO_ROOT / "runtime" / "_internal" / "_effects_impl.py"
HTTP_CLIENT = REPO_ROOT / "runtime" / "_internal" / "effects_clients" / "http_client.py"


def _assert_urlencode_only_inside_helper(path: Path):
    src = path.read_text(encoding="utf-8").splitlines()

    # locate helper definition
    start = None
    indent = None
    for i, line in enumerate(src):
        if line.lstrip().startswith("def _url_with_params("):
            start = i
            indent = len(line) - len(line.lstrip())
            break

    assert start is not None, f"Expected helper def _url_with_params(...) in {path.as_posix()}"

    # find end of function by next top-level def/class with same or меньший indent
    end = len(src)
    for j in range(start + 1, len(src)):
        line = src[j]
        if not line.strip():
            continue
        cur_indent = len(line) - len(line.lstrip())
        if cur_indent <= indent and (line.lstrip().startswith("def ") or line.lstrip().startswith("class ")):
            end = j
            break

    # collect urlencode occurrences
    urlencode_lines = [k for k, line in enumerate(src) if "urlencode(" in line]
    assert urlencode_lines, f"Expected at least one urlencode() usage in {path.as_posix()} (inside helper)"

    outside = [k for k in urlencode_lines if not (start <= k < end)]
    assert outside == [], f"urlencode() must appear only inside _url_with_params() helper; found outside at lines: {outside}"


def test_effects_transport_urlencode_only_in_url_with_params_helper():
    # When transport is split, urlencode may live in http_client instead of effects_impl.
    if "urlencode(" in EFFECTS_IMPL.read_text(encoding="utf-8"):
        _assert_urlencode_only_inside_helper(EFFECTS_IMPL)
    else:
        _assert_urlencode_only_inside_helper(HTTP_CLIENT)
