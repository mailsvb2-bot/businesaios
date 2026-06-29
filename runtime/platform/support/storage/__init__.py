"""Canonical storage support surface with compat alias submodules."""

from __future__ import annotations


from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from runtime.platform.support.storage.base_stores import ArtifactStore, DatasetStore
from runtime.platform.support.storage.generated_stores import *  # noqa: F403
from runtime.platform.support.storage.generated_stores import STORE_TYPES, exported_names, module_basename, store_type


class Store(Protocol):
    def put(self, key: str, value: object) -> None:
        ...

def artifact_name(prefix: str, identifier: str, ext: str) -> str:
    return f"{prefix}_{identifier}.{ext.lstrip('.')}"

def ensure_directory(path: str) -> str:
    Path(path).mkdir(parents=True, exist_ok=True)
    return path

class StorageRetention:
    def keep_latest(self, items: list[str], keep: int) -> list[str]:
        return items[-keep:]

@dataclass(frozen=True)
class StoragePolicy:
    immutable_artifacts: bool = True

def join_uri(prefix: str, suffix: str) -> str:
    return f"{prefix.rstrip('/')}/{suffix.lstrip('/')}"

_ALIAS_EXPORTS = {
    "contracts": "Store",
    "naming": "artifact_name",
    "paths": "ensure_directory",
    "retention": "StorageRetention",
    "storage_policy": "StoragePolicy",
    "uri": "join_uri",
}

__all__ = [
    "ArtifactStore",
    "DatasetStore",
    "STORE_TYPES",
    "StoragePolicy",
    "StorageRetention",
    "Store",
    "artifact_name",
    "ensure_directory",
    "exported_names",
    "join_uri",
    "module_basename",
    "store_type",
] + list(STORE_TYPES) + list(_ALIAS_EXPORTS)
