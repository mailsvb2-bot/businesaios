from __future__ import annotations

import importlib


def test_historical_cli_modules_still_import_and_dispatch() -> None:
    package = importlib.import_module("runtime.platform.support.cli")
    assert package.CLI_ENTRYPOINT is package.cli_main

    audit_module = importlib.import_module("runtime.platform.support.cli.audit")
    train_module = importlib.import_module("runtime.platform.support.cli.train")

    assert callable(audit_module.main)
    assert callable(train_module.main)
