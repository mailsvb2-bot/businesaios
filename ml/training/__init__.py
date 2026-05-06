from __future__ import annotations

import importlib
import sys
from typing import Any

CANON_ML_TRAINING_ALIAS_NAMESPACE = True

_ALIAS_MAP = {
    "offline_training": "learning.trainer",
    "online_update": "learning.policy_update",
    "training_jobs": "learning.trainer",
    "validation": "learning.trainer",
}

_PUBLIC_ATTRS = {
    "OfflineTraining": ("learning.trainer", "OfflineTraining"),
    "OnlineUpdate": ("learning.policy_update", "OnlineUpdate"),
    "TrainingJob": ("learning.trainer", "TrainingJob"),
    "TrainingValidation": ("learning.trainer", "TrainingValidation"),
}


def _install_aliases() -> None:
    package = sys.modules[__name__]
    for alias_name, target in _ALIAS_MAP.items():
        module = importlib.import_module(target)
        sys.modules[f"{__name__}.{alias_name}"] = module
        setattr(package, alias_name, module)


_install_aliases()


def __getattr__(name: str) -> Any:
    target = _PUBLIC_ATTRS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attr_name = target
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


__all__ = ["CANON_ML_TRAINING_ALIAS_NAMESPACE", *sorted(_PUBLIC_ATTRS)]
