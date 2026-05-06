from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE_ROOT = ROOT / "core"

REQUIRED_DOMAIN_FILES = ("contracts.py", "types.py", "errors.py", "service.py")


@dataclass(frozen=True)
class DomainInfo:
    path: Path

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def rel(self) -> str:
        return str(self.path.relative_to(ROOT))


def canonical_domain_dirs() -> list[Path]:
    if not CORE_ROOT.exists():
        return []
    return sorted(
        item for item in CORE_ROOT.iterdir()
        if item.is_dir() and (item / "__canon_domain__.py").exists()
    )


def domain_info_list() -> list[DomainInfo]:
    return [DomainInfo(path=item) for item in canonical_domain_dirs()]


def top_level_files(domain: DomainInfo) -> list[Path]:
    return sorted(path for path in domain.path.iterdir() if path.is_file() and path.suffix == ".py")


def missing_required_files(domain: DomainInfo) -> list[str]:
    present = {path.name for path in top_level_files(domain)}
    return [name for name in REQUIRED_DOMAIN_FILES if name not in present]


def domain_has_any_python(domain: DomainInfo) -> bool:
    return any(domain.path.rglob("*.py"))
