"""Canonical CLI registry.

Entrypoint modules stay as tiny shims for packaging/console-script stability, but
all command naming now flows through one registry surface.
"""

from __future__ import annotations


from runtime.platform.support.command_catalog import CLI_COMMANDS, is_known_cli_command

__all__ = ["CLI_COMMANDS", "is_known_cli_command"]
