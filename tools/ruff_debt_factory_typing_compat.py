"""Compatibility entrypoint for safe typing-related Ruff cleanup.

The actual command-execution owner lives in scripts/maintenance, which is an
approved script surface for raw process execution in the architecture scanner.
"""

from __future__ import annotations

from scripts.maintenance.ruff_debt_factory_typing_compat import main

__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
