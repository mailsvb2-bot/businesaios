from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _scan_roots(root: Path) -> list[Path]:
    """Limit filesystem scans to Python package roots.

    Full-repo rglob can be very slow in some environments (large artifact dirs).
    These roots cover all source trees where Ads ports could realistically exist.
    """

    candidates = [
        root / "core",
        root / "runtime",
        root / "runtime.platform",
        root / "products",
        root / "adapters",
        root / "api",
        root / "scripts",
        root / "tools",
    ]
    return [p for p in candidates if p.exists()]


def _iter_py_files(root: Path) -> Iterable[Path]:
    for base in _scan_roots(root):
        for p in base.rglob("*.py"):
            if any(part in {".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"} for part in p.parts):
                continue
            yield p


def _read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def test_ads_service_is_single_source_of_truth() -> None:
    """Canon rule: exactly one AdsService definition in core/ads/ads_service.py."""

    root = _repo_root()
    canon_path = root / "core" / "ads" / "ads_service.py"
    assert canon_path.exists(), "Canonical core/ads/ads_service.py is missing"

    # 1) Ensure only one file named ads_service.py exists (excluding tests)
    all_ads_service_files = []
    for base in _scan_roots(root):
        for p in base.rglob("ads_service.py"):
            if "tests" in p.parts:
                continue
            all_ads_service_files.append(p)

    if len(all_ads_service_files) != 1 or all_ads_service_files[0].resolve() != canon_path.resolve():
        found = [str(p.relative_to(root)) for p in all_ads_service_files]
        raise AssertionError(
            "Found multiple ads_service.py files or canonical path mismatch.\n"
            f"Expected only: {canon_path.relative_to(root)}\n"
            f"Found: {found}"
        )

    # 2) Ensure AdsService class exists only once in repository (excluding tests)
    hits: list[tuple[str, int, str]] = []
    for p in _iter_py_files(root):
        if "tests" in p.parts:
            continue
        text = _read_text(p)
        if not text:
            continue
        for idx, line in enumerate(text.splitlines(), start=1):
            s = line.strip()
            if s.startswith("class AdsService"):
                hits.append((str(p.relative_to(root)), idx, s))

    if len(hits) != 1:
        msg = ["Expected exactly one 'class AdsService' in repo (excluding tests). Found:", ""]
        for rel, ln, s in hits[:50]:
            msg.append(f"- {rel}:{ln}: {s}")
        if len(hits) > 50:
            msg.append(f"... and {len(hits)-50} more")
        msg.append("")
        msg.append("Fix: keep only core/ads/ads_service.py::AdsService; rename other implementations.")
        raise AssertionError("\n".join(msg))

    only_rel, _, _ = hits[0]
    if (root / only_rel).resolve() != canon_path.resolve():
        raise AssertionError(
            "AdsService class found outside canonical location.\n"
            f"Canonical: {canon_path.relative_to(root)}\n"
            f"Found in: {only_rel}\n"
            "Fix: move/rename the non-canonical AdsService."
        )


def test_core_has_no_secondary_ads_ports() -> None:
    """Guard: Ads port surface must not be reintroduced elsewhere in core/."""

    root = _repo_root()
    canon = root / "core" / "ads" / "ads_service.py"
    core_dir = root / "core"
    assert core_dir.exists()

    allowed_file = canon.resolve()
    # Match exact port surface names only (avoid false positives like build_plan_confirmation_text).
    suspicious_prefixes = {"def build_plan(", "def apply_plan(", "def metrics("}

    hits: list[tuple[str, int, str]] = []
    for p in _iter_py_files(core_dir):
        if p.resolve() == allowed_file:
            continue
        text = _read_text(p)
        if not text:
            continue
        for idx, line in enumerate(text.splitlines(), start=1):
            s = line.strip()
            if not s.startswith("def "):
                continue
            for token in suspicious_prefixes:
                if s.startswith(token):
                    hits.append((str(p.relative_to(root)), idx, s))
                    break

    if hits:
        msg = ["Found secondary Ads port-like methods in core/ (non-canonical):", ""]
        for rel, ln, s in hits[:50]:
            msg.append(f"- {rel}:{ln}: {s}")
        if len(hits) > 50:
            msg.append(f"... and {len(hits)-50} more")
        msg.append("")
        msg.append("Fix: route Ads operations through core.ads.AdsService only.")
        raise AssertionError("\n".join(msg))


def test_runtime_platform_does_not_import_core_ads_service() -> None:
    """Layer boundary: runtime.platform must not depend on core.ads.ads_service."""

    root = _repo_root()
    pl = root / "runtime" / "platform"
    if not pl.exists():
        return

    bad: list[tuple[str, int, str]] = []
    for p in _iter_py_files(pl):
        text = _read_text(p)
        if not text:
            continue
        for idx, line in enumerate(text.splitlines(), start=1):
            s = line.strip()
            if not (s.startswith("import ") or s.startswith("from ")):
                continue
            if "core.ads.ads_service" in s or "core.ads" in s and "ads_service" in s:
                bad.append((str(p.relative_to(root)), idx, s))

    if bad:
        msg = ["runtime.platform must not import core AdsService (reverse dependency):", ""]
        for rel, ln, s in bad[:50]:
            msg.append(f"- {rel}:{ln}: {s}")
        if len(bad) > 50:
            msg.append(f"... and {len(bad)-50} more")
        msg.append("")
        msg.append("Fix: keep AdsService in core; runtime/platform provides adapters/providers only.")
        raise AssertionError("\n".join(msg))
