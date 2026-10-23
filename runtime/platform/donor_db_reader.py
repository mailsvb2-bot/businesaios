"""Read-only reader of a legacy donor SQLite DB for one-shot migration."""

from __future__ import annotations

import sqlite3
from typing import Any

TABLES = (
    "business_offerings",
    "customers",
    "business_offering_prices",
    "booking_slots",
    "business_payments",
    "clientplatform_sales_leads",
    "partner_candidates",
    "business_publications",
    "business_members",
)


def read_donor(path: str, business_id: str) -> dict[str, list[dict[str, Any]]]:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {
            t: [dict(r) for r in conn.execute(f"SELECT * FROM {t} WHERE business_id=?", (business_id,))]  # noqa: S608
            for t in TABLES
            if t in have
        }
    finally:
        conn.close()
