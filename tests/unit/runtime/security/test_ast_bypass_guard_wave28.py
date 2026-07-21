from __future__ import annotations

import ast
from pathlib import Path

import pytest

import runtime.security.ast_bypass_guard as guard
from canon.repository_sources import RepositorySourceError


def _violations(source: str, *, rel: str = "core/example.py") -> list[str]:
    visitor = guard._Visitor(rel)
    visitor.visit(ast.parse(source))
    return visitor.violations


def test_allowed_files_and_import_rules() -> None:
    assert guard._is_allowed_file("runtime/_internal/client.py") is True
    assert guard._is_allowed_file("runtime/executor.py") is True
    assert guard._is_allowed_file("runtime/admin_state_support.py") is True
    assert guard._is_allowed_file("core/service.py") is False

    violations = _violations(
        """
import runtime._internal.client
import harmless
import requests
import subprocess
from runtime._internal import client
from httpx import Client
from package import *
from .relative import harmless
"""
    )
    assert any("runtime._internal.client" in item for item in violations)
    assert any("import requests" in item for item in violations)
    assert any("import subprocess" in item for item in violations)
    assert any("from runtime._internal" in item for item in violations)
    assert any("from httpx" in item for item in violations)
    assert not any("relative" in item for item in violations)

    assert (
        _violations(
            "import requests\nfrom httpx import Client\n",
            rel=guard.ALLOWED_NETWORK_FILE,
        )
        == []
    )
    allowed_private = _violations(
        "import runtime._internal.client\nfrom runtime._internal import client\n",
        rel="runtime/executor.py",
    )
    assert allowed_private == []
    assert _violations("import subprocess\n", rel=guard.ALLOWED_NETWORK_FILE)
    assert _violations("from urllib.parse import urlparse\n") == []
    assert _violations("from urllib import parse\n") == []
    assert _violations("from urllib import request\n")
    assert _violations("import urllib.request\n")


def test_call_rules_cover_static_dynamic_and_nested_bypasses() -> None:
    violations = _violations(
        """
send_message('x')
importlib.import_module('runtime._internal.client')
__import__('runtime._internal.client')
getattr(runtime, '_internal')
wrapper(send_message('nested'))
"""
    )
    assert sum("call send_message" in item for item in violations) == 2
    assert sum("dynamic import" in item for item in violations) == 2
    assert any("getattr" in item for item in violations)

    alias_violations = _violations(
        "from subprocess import run as shell_run\n"
        "import subprocess as sp\n"
        "from socket import connect as socket_connect\n"
        "shell_run([])\nsp.check_call([])\nsocket_connect()\n"
    )
    assert any("call shell_run" in item for item in alias_violations)
    assert any("call subprocess.check_call" in item for item in alias_violations)
    assert any("call socket_connect" in item for item in alias_violations)
    assert _violations("def connect(): pass\nconnect()\n") == []

    harmless = _violations(
        """
importlib.import_module(module_name)
importlib.import_module('public.module')
__import__(module_name)
__import__('public.module')
getattr(runtime, name)
getattr(runtime)
(factory())()
"""
    )
    assert harmless == []
    assert (
        _violations(
            "importlib.import_module('runtime._internal.client')\n",
            rel="runtime/admin_state_support.py",
        )
        == []
    )
    assert (
        _violations(
            "__import__('runtime._internal.client')\ngetattr(runtime, '_internal')\n",
            rel="runtime/_internal/adapter.py",
        )
        == []
    )


def test_scan_repo_preserves_clean_contract_and_reports_all_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "core").mkdir()
    (root / "core" / "clean.py").write_text("value = 1\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "ignored.py").write_text("import requests\n", encoding="utf-8")
    (root / "runtime" / "_internal").mkdir(parents=True)
    (root / "runtime" / "_internal" / "ignored.py").write_text("import requests\n", encoding="utf-8")
    assert guard.scan_repo(root) is None

    (root / "core" / "bad.py").write_text("import requests\nsend_message('x')\n", encoding="utf-8")
    (root / "core" / "syntax.py").write_text("def broken(:\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="DECISION_BYPASS_DETECTED") as exc_info:
        guard.scan_repo(root)
    message = str(exc_info.value)
    assert "import requests" in message
    assert "call send_message" in message
    assert "SYNTAX_ERROR" in message
    assert message.splitlines()[1:] == sorted(set(message.splitlines()[1:]))

    with pytest.raises(RuntimeError, match="SCAN_ROOT_ERROR"):
        guard.scan_repo(root / "missing")

    real_read = guard.read_utf8_source

    def broken_read(path: Path) -> str:
        if path.name == "clean.py":
            error = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad")
            raise RepositorySourceError("failed") from error
        return real_read(path)

    monkeypatch.setattr(guard, "read_utf8_source", broken_read)
    with pytest.raises(RuntimeError, match="SOURCE_READ_ERROR: UnicodeDecodeError"):
        guard.scan_repo(root)

    def broken_inventory(*_args: object, **_kwargs: object):
        raise RepositorySourceError("inventory failed")
        yield  # pragma: no cover

    monkeypatch.setattr(guard, "iter_repository_python_files", broken_inventory)
    with pytest.raises(RuntimeError, match="SOURCE_SCAN_ERROR: inventory failed"):
        guard.scan_repo(root)
