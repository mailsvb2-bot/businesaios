from __future__ import annotations

from tests.arch._canon_master_audit_guard import (
    manifest_has_required_pack_ids,
    master_checklist_exists,
    master_checklist_has_markers,
    meta_core_files_have_master_visibility,
    required_files_exist,
    snapshot,
)


def test_master_audit_stack_is_consistent() -> None:
    missing_files = required_files_exist()
    missing_pack_ids = manifest_has_required_pack_ids()
    visibility_offenders = meta_core_files_have_master_visibility()
    assert master_checklist_exists(), "Missing docs/CANON_MASTER_CHECKLIST_V1.md."
    assert master_checklist_has_markers(), "docs/CANON_MASTER_CHECKLIST_V1.md must contain CANON_META_PACK and CANON_MASTER_LAYER."
    assert not missing_files, "Master audit found missing constitutional files. Missing:\n- " + "\n- ".join(missing_files)
    assert not missing_pack_ids, "Master audit found missing required pack IDs in meta-pack manifest. Missing:\n- " + "\n- ".join(missing_pack_ids)
    assert not visibility_offenders, "Master audit found missing CANON_META_PACK visibility. Offenders:\n- " + "\n- ".join(visibility_offenders)
    state = snapshot()
    assert state.required_doc_count >= 10
    assert state.required_helper_count >= 8
    assert state.required_test_count >= 12
    assert state.manifest_pack_count >= 10
