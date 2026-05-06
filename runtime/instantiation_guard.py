from __future__ import annotations

import inspect
from pathlib import Path

from canon.runtime_factory_rules import ALLOWED_FACTORY_MODULES


def assert_runtime_instantiation_allowed(target_name: str) -> None:
    stack = inspect.stack()

    for frame_info in stack[1:]:
        filename = Path(frame_info.filename).as_posix()
        if _is_allowed_factory_path(filename):
            return

    raise RuntimeError(
        f"Illegal manual instantiation of runtime-critical object '{target_name}'. "
        "Use canonical boot factory/registration path."
    )


def _is_allowed_factory_path(filename: str) -> bool:
    normalized = filename.replace("\\", "/")
    return any(normalized.endswith(path) for path in ALLOWED_FACTORY_MODULES)
