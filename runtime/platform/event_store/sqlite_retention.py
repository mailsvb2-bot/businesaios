"""Retention-SaaS helpers for SqliteEventStore.

Bandit arms, daily feature snapshots, and distributed job locks.
Extracted from sqlite_event_store.py.
"""

from __future__ import annotations


import sqlite3



def upsert_user_features_daily(
    db: sqlite3.Connection,
    *,
    tenant_id: str,
    user_id: str,
    day_key: str,
    features_json: str,
    created_at_ms: int,
) -> None:
    db.execute(
        "INSERT INTO user_features_daily(tenant_id,user_id,day_key,features_json,created_at_ms) "
        "VALUES(?,?,?,?,?) "
        "ON CONFLICT(tenant_id,user_id,day_key) DO UPDATE SET "
        "features_json=excluded.features_json, created_at_ms=excluded.created_at_ms",
        (str(tenant_id), str(user_id), str(day_key), str(features_json), int(created_at_ms)),
    )
    db.commit()


def get_user_features_daily(
    db: sqlite3.Connection,
    *,
    tenant_id: str,
    user_id: str,
    day_key: str,
) -> str | None:
    row = db.execute(
        "SELECT features_json FROM user_features_daily WHERE tenant_id=? AND user_id=? AND day_key=?",
        (str(tenant_id), str(user_id), str(day_key)),
    ).fetchone()
    return str(row[0]) if row and row[0] is not None else None


def bandit_ensure_arm(db: sqlite3.Connection, *, tenant_id: str, arm: str, now_ms: int) -> None:
    db.execute(
        "INSERT OR IGNORE INTO bandit_arms(tenant_id,arm,alpha,beta,last_updated_at_ms) VALUES(?,?,1.0,1.0,?)",
        (str(tenant_id), str(arm), int(now_ms)),
    )
    db.commit()


def bandit_get_arm(db: sqlite3.Connection, *, tenant_id: str, arm: str) -> tuple[float, float]:
    row = db.execute(
        "SELECT alpha,beta FROM bandit_arms WHERE tenant_id=? AND arm=?",
        (str(tenant_id), str(arm)),
    ).fetchone()
    if not row:
        return (1.0, 1.0)
    return (float(row[0] or 1.0), float(row[1] or 1.0))


def bandit_update_arm(db: sqlite3.Connection, *, tenant_id: str, arm: str, success: bool, now_ms: int) -> None:
    bandit_ensure_arm(db, tenant_id=tenant_id, arm=arm, now_ms=now_ms)
    if bool(success):
        db.execute(
            "UPDATE bandit_arms SET alpha=alpha+1, last_updated_at_ms=? WHERE tenant_id=? AND arm=?",
            (int(now_ms), str(tenant_id), str(arm)),
        )
    else:
        db.execute(
            "UPDATE bandit_arms SET beta=beta+1, last_updated_at_ms=? WHERE tenant_id=? AND arm=?",
            (int(now_ms), str(tenant_id), str(arm)),
        )
    db.commit()


def try_lock_job(db: sqlite3.Connection, *, tenant_id: str, job_key: str, now_ms: int) -> bool:
    try:
        db.execute(
            "INSERT INTO job_locks(tenant_id,job_key,locked_at_ms) VALUES(?,?,?)",
            (str(tenant_id), str(job_key), int(now_ms)),
        )
        db.commit()
        return True
    except Exception:
        return False
