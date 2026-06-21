from __future__ import annotations

import ast
from pathlib import Path


def test_locklease_has_single_contract_owner() -> None:
    root = Path.cwd()
    owners: list[str] = []

    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith((".git/", ".venv/", "venv/", "__pycache__/")):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "LockLease":
                owners.append(rel)

    assert owners == ["reliability/distributed_lock_contracts.py"]


def test_locklease_public_routes_are_same_object() -> None:
    from reliability import LockLease as PackageRoute
    from reliability.distributed_lock import LockLease as PublicRoute
    from reliability.distributed_lock_contracts import LockLease as OwnerRoute

    assert PackageRoute is OwnerRoute
    assert PublicRoute is OwnerRoute
    assert OwnerRoute.__module__ == "reliability.distributed_lock_contracts"


def test_distributed_lock_backends_depend_on_contract_owner() -> None:
    root = Path.cwd()

    backend_files = [
        root / "reliability/distributed_lock_backend.py",
        root / "reliability/distributed_lock_postgres.py",
        root / "reliability/distributed_lock_redis.py",
    ]

    for path in backend_files:
        text = path.read_text(encoding="utf-8")
        assert "from reliability.distributed_lock_contracts import LockLease" in text
        assert "from reliability.distributed_lock import LockLease" not in text
