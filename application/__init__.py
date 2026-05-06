from __future__ import annotations

"""Restored canonical application namespace.

This archive was missing the application owner package. The modules restored here
provide the canonical import surface expected by runtime/core entrypoints while
keeping the actual logic delegated to the existing owner implementations that are
present in this tree.
"""
