from __future__ import annotations
"""Compatibility import for the canonical PostgresPort.
Ownership now lives in ``runtime.platform.postgres_port`` so the project has a
single Postgres transport contract. This module intentionally re-exports the
canonical implementation for legacy imports.
"""
from runtime.platform.postgres_port import PostgresPort
__all__ = ["PostgresPort"]
