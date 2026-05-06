from __future__ import annotations

import hashlib


def _sha256_hex(s: str) -> str:
    h = hashlib.sha256()
    h.update(s.encode("utf-8"))
    return h.hexdigest()


def canonical_node_id(*, node_type: str, key: str) -> str:
    """Deterministic node id."""
    nt = str(node_type).strip().lower()
    k = str(key).strip()
    return "n_" + _sha256_hex(f"{nt}|{k}")[:24]


def canonical_edge_id(*, edge_type: str, src: str, dst: str, salt: str = "") -> str:
    """Deterministic edge id."""
    et = str(edge_type).strip().lower()
    s = str(src).strip()
    d = str(dst).strip()
    slt = str(salt or "").strip()
    return "e_" + _sha256_hex(f"{et}|{s}|{d}|{slt}")[:24]
