from __future__ import annotations

import boot
import boot.runtime_public_api as runtime_public_api
import runtime.bootstrap.runtime_builder as runtime_builder


class _Artifacts:
    built_runtime = object()


class _Runtime:
    artifacts = _Artifacts()


def test_boot_package_build_runtime_uses_sovereign_owner(monkeypatch) -> None:
    monkeypatch.setattr(
        "runtime.bootstrap.sovereign_bootstrap.bootstrap_runtime",
        lambda *args, **kwargs: _Runtime(),
    )
    assert boot.build_runtime() is _Artifacts.built_runtime


def test_boot_package_built_runtime_points_to_runtime_builder_type() -> None:
    assert boot.BuiltRuntime is runtime_builder.BuiltRuntime


def test_runtime_public_api_built_runtime_points_to_runtime_builder_type() -> None:
    assert runtime_public_api.BuiltRuntime is runtime_builder.BuiltRuntime
