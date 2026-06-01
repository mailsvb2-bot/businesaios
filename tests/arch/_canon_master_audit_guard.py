from __future__ import annotations

# CANON_META_PACK: helper is part of the repository engineering constitution.
# CANON_MASTER_LAYER: this helper checks the full constitutional stack as one system.
from dataclasses import dataclass
from pathlib import Path

from tests.arch._canon_arch_audit_index import REQUIRED_DOCS, REQUIRED_HELPERS, REQUIRED_TESTS, absolute_path
from tests.arch._canon_meta_pack_guard import REQUIRED_PACK_IDS, load_manifest

ROOT = Path(__file__).resolve().parents[2]
MASTER_CHECKLIST_PATH = ROOT / "docs" / "CANON_MASTER_CHECKLIST_V1.md"

@dataclass(frozen=True)
class MasterAuditSnapshot:
    required_doc_count: int
    required_helper_count: int
    required_test_count: int
    manifest_pack_count: int

def required_files_exist() -> list[str]:
    missing = []
    for item in (*REQUIRED_DOCS, *REQUIRED_HELPERS, *REQUIRED_TESTS):
        if not absolute_path(item.rel).exists():
            missing.append(item.rel)
    return missing

def manifest_has_required_pack_ids() -> list[str]:
    manifest = load_manifest()
    actual = {pack.pack_id for pack in manifest.packs}
    return [pack_id for pack_id in REQUIRED_PACK_IDS if pack_id not in actual]

def master_checklist_exists() -> bool:
    return MASTER_CHECKLIST_PATH.exists()

def master_checklist_has_markers() -> bool:
    if not MASTER_CHECKLIST_PATH.exists():
        return False
    text = MASTER_CHECKLIST_PATH.read_text(encoding="utf-8")
    return "CANON_META_PACK" in text and "CANON_MASTER_LAYER" in text

def meta_core_files_have_master_visibility() -> list[str]:
    target_files = (
        ROOT / "docs" / "CANON_META_PACK_INDEX_V1.md",
        ROOT / "docs" / "CANON_ONBOARDING_FOR_ARCHITECTS_V1.md",
        ROOT / "docs" / "CANON_META_PACK_MANIFEST_V1.yaml",
        ROOT / "docs" / "CANON_MASTER_CHECKLIST_V1.md",
        ROOT / "tests" / "arch" / "_canon_meta_pack_guard.py",
        ROOT / "tests" / "arch" / "_canon_master_audit_guard.py",
    )
    offenders = []
    for path in target_files:
        if not path.exists():
            offenders.append(str(path.relative_to(ROOT)))
            continue
        text = path.read_text(encoding="utf-8")
        if "CANON_META_PACK" not in text:
            offenders.append(str(path.relative_to(ROOT)))
    return offenders

def snapshot() -> MasterAuditSnapshot:
    manifest = load_manifest()
    return MasterAuditSnapshot(
        required_doc_count=len(REQUIRED_DOCS),
        required_helper_count=len(REQUIRED_HELPERS),
        required_test_count=len(REQUIRED_TESTS),
        manifest_pack_count=len(manifest.packs),
    )
