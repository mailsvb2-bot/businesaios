from __future__ import annotations

from collections.abc import Mapping
from importlib import import_module


def assert_world_state_boundary(advisory_flags: Mapping[str, str]) -> None:
    fn = import_module("canon.integration_boundaries").assert_world_state_boundary
    fn(advisory_flags)


__all__ = ["assert_world_state_boundary"]
