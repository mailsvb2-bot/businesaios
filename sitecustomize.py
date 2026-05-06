"""Safe repository-wide Python startup defaults.

This file is imported implicitly by Python when the repository root is on
``sys.path``.  It must stay dependency-free: importing project packages here can
make even ``python -c 'print(1)'`` execute runtime boot code or hang before the
requested program starts.
"""
from __future__ import annotations
import os
import sys
import warnings

sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
os.environ.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
os.environ.setdefault("DD_TRACE_ENABLED", "0")
os.environ.setdefault("DD_TRACE_STARTUP_LOGS", "0")

warnings.filterwarnings(
    "ignore",
    message=r"Please use `import python_multipart` instead\.",
    category=PendingDeprecationWarning,
)
