from .canon.architecture_constitution import ARCHITECTURE_NAME

__all__ = ["ARCHITECTURE_NAME"]
from runtime.platform.support.import_doors import (
    install_runtime_platform_support_import_doors as _install_runtime_platform_support_import_doors,
)

_install_runtime_platform_support_import_doors()
