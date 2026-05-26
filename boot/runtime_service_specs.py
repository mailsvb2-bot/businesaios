from __future__ import annotations

"""Compatibility shell for canonical runtime service specs.

The canonical owner is bootstrap.runtime_service_specs. This file keeps legacy
boot imports working without defining an independent service-spec catalog or
runtime assembly path.
"""

CANON_BOOT_RUNTIME_SERVICE_SPECS_COMPAT_SHELL = True
CANON_BOOT_RUNTIME_SERVICE_SPECS_NO_RUNTIME_ASSEMBLY = True

from bootstrap.runtime_service_specs import *  # noqa: F401,F403
from bootstrap.runtime_service_specs import (
    RUNTIME_BOOT_SERVICE_SPECS,
    RUNTIME_BOOT_SERVICE_SPEC_BY_CALLABLE,
    RUNTIME_BOOT_SERVICE_SPEC_BY_NAME,
)

RUNTIME_SERVICE_SPECS = RUNTIME_BOOT_SERVICE_SPECS
RUNTIME_SERVICE_SPEC_BY_CALLABLE = RUNTIME_BOOT_SERVICE_SPEC_BY_CALLABLE
RUNTIME_SERVICE_SPEC_BY_NAME = RUNTIME_BOOT_SERVICE_SPEC_BY_NAME
