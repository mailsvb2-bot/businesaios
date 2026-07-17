from __future__ import annotations

from scripts.ci import step_demo_e2e_smoke


def test_cleanup_removes_database_files_and_sidecars_across_runtime_roots(
    tmp_path,
    monkeypatch,
) -> None:
    external_demo = tmp_path / "external-ci-demo"
    external_demo.mkdir()
    (external_demo / "state.db").write_text("temporary", encoding="utf-8")

    removable = (
        tmp_path / ".runtime" / "root.sqlite3",
        tmp_path / ".runtime" / "root.sqlite3-wal",
        tmp_path / "data" / "runtime" / "queue" / "queue.db",
        tmp_path / "data" / "tenancy" / "tenant.sqlite-shm",
        tmp_path / "runtime" / "data" / "demo" / "demo.db",
        tmp_path / "runtime" / "data" / "demo" / "demo.db-wal",
        tmp_path / "runtime" / "data" / "test" / "test.sqlite3",
        tmp_path / "runtime" / "data" / "test" / "test.sqlite3-journal",
    )
    for path in removable:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("temporary", encoding="utf-8")

    retained = tmp_path / "runtime" / "data" / "demo" / "README.txt"
    retained.write_text("keep", encoding="utf-8")

    monkeypatch.setattr(step_demo_e2e_smoke, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_demo_e2e_smoke, "_CI_DEMO_STATE_ROOT", external_demo)

    removed = step_demo_e2e_smoke.cleanup_ci_runtime_state()

    for path in removable:
        assert not path.exists()
    assert retained.read_text(encoding="utf-8") == "keep"
    assert not external_demo.exists()
    assert "runtime/data/demo/demo.db" in removed
    assert "runtime/data/test/test.sqlite3-journal" in removed
    assert str(external_demo) in removed
