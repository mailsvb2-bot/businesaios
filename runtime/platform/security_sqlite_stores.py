from __future__ import annotations

import sqlite3
from pathlib import Path

CANON_PLATFORM_SECURITY_SQLITE_STORES = True


def _ensure_parent(db_path: str) -> None:
    Path(str(db_path)).parent.mkdir(parents=True, exist_ok=True)


def open_security_sqlite_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


from runtime.platform.security_sqlite_backends.group_01 import (SQLiteGovernanceJournalStore, SQLiteSimpleAuditEventStoreBackend, SQLiteSecurityAuditChainBackend, SQLiteTokenRevocationStoreBackend, SQLiteSecurityDrillScheduleStoreBackend, SQLiteKMSProviderBackend)
from runtime.platform.security_sqlite_backends.group_02 import (SQLiteReencryptionProgressLedgerBackend, SQLiteKeyRotationJournalBackend, SQLiteSecurityIncidentRegistryBackend, SQLiteApprovalReplayGuardBackend, SQLiteSecurityQuarantineRegistryBackend, SQLiteReencryptionJobStoreBackend)
from runtime.platform.security_sqlite_backends.group_03 import (SQLiteSecurityIncidentDrillHistoryBackend, SignedOperatorApprovalStoreBackend, SQLiteSecurityOperatorWorkflowStoreBackend)

__all__ = [
    "CANON_PLATFORM_SECURITY_SQLITE_STORES",
    "open_security_sqlite_connection",
    "SQLiteGovernanceJournalStore",
    "SQLiteSimpleAuditEventStoreBackend",
    "SQLiteSecurityAuditChainBackend",
    "SQLiteTokenRevocationStoreBackend",
    "SQLiteSecurityDrillScheduleStoreBackend",
    "SQLiteKMSProviderBackend",
    "SQLiteReencryptionProgressLedgerBackend",
    "SQLiteKeyRotationJournalBackend",
    "SQLiteSecurityIncidentRegistryBackend",
    "SQLiteApprovalReplayGuardBackend",
    "SQLiteSecurityQuarantineRegistryBackend",
    "SQLiteReencryptionJobStoreBackend",
    "SQLiteSecurityIncidentDrillHistoryBackend",
    "SignedOperatorApprovalStoreBackend",
    "SQLiteSecurityOperatorWorkflowStoreBackend",
]
