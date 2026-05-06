from __future__ import annotations

from dataclasses import dataclass

from boot.runtime_public_api import build_runtime


@dataclass(frozen=True)
class _Artifacts:
    built_runtime: object


@dataclass(frozen=True)
class _Runtime:
    artifacts: _Artifacts


def test_build_runtime_delegates_to_bootstrap_runtime(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_bootstrap_runtime(*, project_root=None):
        captured["project_root"] = project_root
        return _Runtime(artifacts=_Artifacts(built_runtime={"ok": True}))

    monkeypatch.setattr("runtime.bootstrap.sovereign_bootstrap.bootstrap_runtime", _fake_bootstrap_runtime)
    assert build_runtime(project_root="/tmp/proj") == {"ok": True}
    assert captured == {"project_root": "/tmp/proj"}
