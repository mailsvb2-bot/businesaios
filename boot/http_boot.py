from importlib import import_module

CANON_LEGACY_BOOTSTRAP_SHIM = True
CANON_HTTP_BOOT_THIN_SHIM = True
CANON_HTTP_BOOT_NO_RUNTIME_ASSEMBLY = True
CANON_HTTP_BOOT_DIRECT_OWNER_DELEGATION = True
CANON_HTTP_BOOT_SINGLE_SURFACE_DELEGATION = True
CANON_HTTP_BOOT_DIRECT_BOOTSTRAP_HTTP_SURFACE = True
CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "bootstrap.http_boot_surface"


def _load_attr(module_name, attr_name):
    return getattr(import_module(module_name), attr_name)


def boot_application():
    return _load_attr("bootstrap.http_boot_surface", "build_http_boot_surface")().http_app


def boot_http_app():
    return boot_application()
