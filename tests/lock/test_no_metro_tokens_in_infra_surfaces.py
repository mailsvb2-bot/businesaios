from __future__ import annotations

import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_no_legacy_metro_tokens_in_infra_surfaces() -> None:
    """Rebrand-safety lock.

    The repository may legitimately include a connected product named 'organization_platform'.
    This lock targets *infra/config/runtime* surfaces where legacy ids (metro_, metro-, metro/ or standalone 'metro')
    are a deployment/ops risk.
    """

    rx = re.compile(r"(?i)(?:\bmetro\b|metro[_/\-])")

    roots = [
        REPO_ROOT / "infra",
        REPO_ROOT / "runtime",
        REPO_ROOT / "scripts",
        REPO_ROOT / "runtime.platform",
        REPO_ROOT / "core" / "config",
        REPO_ROOT / "main.py",
        REPO_ROOT / ".env.example",
        REPO_ROOT / "docker-compose.yml",
    ]

    allow_files = {
        # Allowed to mention legacy ids in the contract docs.
        (REPO_ROOT / "docs" / "DEPLOYMENT_CONTRACT.md").resolve(),
        # Telegram product aliases are allowed (user-facing shortcut, not infra drift).
        (REPO_ROOT / "interfaces" / "telegram" / "pipeline" / "update_processor.py").resolve(),
    }

    hits: list[str] = []

    def iter_targets() -> list[pathlib.Path]:
        out: list[pathlib.Path] = []
        for r in roots:
            if not r.exists():
                continue
            if r.is_file():
                out.append(r)
            else:
                out.extend([p for p in r.rglob("*") if p.is_file()])
        return out

    for p in iter_targets():
        if p.resolve() in allow_files:
            continue
        if any(part in {".git", ".venv", "venv", "__pycache__", ".pytest_cache"} for part in p.parts):
            continue
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".sqlite", ".db"}:
            continue
        if p.stat().st_size > 2_000_000:
            continue

        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        if rx.search(text):
            hits.append(p.relative_to(REPO_ROOT).as_posix())

    assert not hits, "Legacy metro identifiers found in infra/config surfaces:\n" + "\n".join(sorted(set(hits))[:200])
