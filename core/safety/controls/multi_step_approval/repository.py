from __future__ import annotations

import json
import sqlite3
from collections.abc import MutableMapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from sqlite3 import Connection
from threading import RLock
from typing import Iterator, Protocol

from ..support.sqlite_migrations import SafetySqliteMigrator, SchemaMigrationPlan
from .models import ApprovalTicket, ApprovalWorkflowState

CANON_SAFETY_APPROVAL_REPOSITORY = True
SCHEMA_VERSION = 6


class ApprovalRepository(Protocol):
    def get(self, action_id: str) -> ApprovalTicket: ...
    def put(self, ticket: ApprovalTicket) -> None: ...
    def record_approval(self, *, action_id: str, approver: str) -> ApprovalTicket: ...
    def record_rejection(self, *, action_id: str, approver: str) -> ApprovalTicket: ...
    def mark_executed(self, *, action_id: str) -> ApprovalTicket: ...


@dataclass
class InMemoryApprovalRepository:
    tickets: dict[str, ApprovalTicket] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def get(self, action_id: str) -> ApprovalTicket:
        with self._lock:
            return self.tickets.get(str(action_id), ApprovalTicket(action_id=str(action_id)))

    def put(self, ticket: ApprovalTicket) -> None:
        with self._lock:
            current = self.tickets.get(str(ticket.action_id))
            version = int(ticket.version if ticket.version else ((current.version + 1) if current else 1))
            self.tickets[str(ticket.action_id)] = ApprovalTicket(**{**ticket.__dict__, 'version': version})

    def acquire_lease(self, *, action_id: str, owner: str) -> ApprovalTicket:
        with self._lock:
            current = self.get(action_id)
            leased = ApprovalTicket(**{**current.__dict__, 'lease_owner': str(owner), 'version': int(current.version) + 1, 'fencing_token': int(current.fencing_token) + 1})
            self.tickets[str(action_id)] = leased
            return leased

    def compare_and_set(self, *, expected_version: int, ticket: ApprovalTicket) -> ApprovalTicket:
        with self._lock:
            current = self.get(ticket.action_id)
            if int(current.version) != int(expected_version):
                raise RuntimeError('approval_ticket_version_conflict')
            if current.lease_owner and ticket.lease_owner and current.lease_owner != ticket.lease_owner and int(ticket.fencing_token or 0) < int(current.fencing_token or 0):
                raise RuntimeError('approval_ticket_stale_fencing_token')
            updated = ApprovalTicket(
                **{**ticket.__dict__, 'version': int(expected_version) + 1, 'fencing_token': max(int(ticket.fencing_token or 0), int(current.fencing_token or 0))}
            )
            self.tickets[str(ticket.action_id)] = updated
            return updated

    def record_approval(self, *, action_id: str, approver: str) -> ApprovalTicket:
        action_key = str(action_id).strip()
        approver_key = str(approver).strip()
        if not action_key or not approver_key:
            raise ValueError('action_id and approver are required')
        with self._lock:
            current = self.tickets.get(action_key, ApprovalTicket(action_id=action_key))
            approvals = tuple(dict.fromkeys([*current.approvals, approver_key]))
            required = max(int(current.required_approvals or 0), 2)
            state = current.state
            if current.state is not ApprovalWorkflowState.REJECTED:
                state = ApprovalWorkflowState.APPROVED if len(approvals) >= required else ApprovalWorkflowState.PARTIALLY_APPROVED
            ticket = ApprovalTicket(
                action_id=action_key,
                approvals=approvals,
                state=state,
                rejections=current.rejections,
                requested_by=current.requested_by,
                expires_at=current.expires_at,
                required_approvals=required,
                escalation_level=current.escalation_level,
                version=int(current.version) + 1,
                lease_owner=current.lease_owner,
                fencing_token=current.fencing_token,
            )
            self.tickets[action_key] = ticket
            return ticket

    def record_rejection(self, *, action_id: str, approver: str) -> ApprovalTicket:
        action_key = str(action_id).strip()
        approver_key = str(approver).strip()
        current = self.tickets.get(action_key, ApprovalTicket(action_id=action_key))
        rejections = tuple(dict.fromkeys([*current.rejections, approver_key]))
        ticket = ApprovalTicket(
            action_id=action_key,
            approvals=current.approvals,
            state=ApprovalWorkflowState.REJECTED,
            rejections=rejections,
            requested_by=current.requested_by,
            expires_at=current.expires_at,
            required_approvals=current.required_approvals,
            escalation_level=current.escalation_level,
            version=int(current.version) + 1,
            lease_owner=current.lease_owner,
            fencing_token=current.fencing_token,
        )
        self.tickets[action_key] = ticket
        return ticket

    def mark_executed(self, *, action_id: str) -> ApprovalTicket:
        action_key = str(action_id).strip()
        current = self.tickets.get(action_key, ApprovalTicket(action_id=action_key))
        executed = ApprovalTicket(
            action_id=current.action_id,
            approvals=current.approvals,
            state=ApprovalWorkflowState.EXECUTED,
            rejections=current.rejections,
            requested_by=current.requested_by,
            expires_at=current.expires_at,
            required_approvals=current.required_approvals,
            escalation_level=current.escalation_level,
            version=int(current.version) + 1,
            lease_owner=current.lease_owner,
            fencing_token=current.fencing_token,
        )
        self.tickets[action_key] = executed
        return executed


class _ApprovalTicketMap(MutableMapping[str, ApprovalTicket]):
    def __init__(self, repo: 'SqliteApprovalRepository') -> None:
        self._repo = repo

    def __getitem__(self, key: str) -> ApprovalTicket:
        return self._repo.get(key)

    def __setitem__(self, key: str, value: ApprovalTicket) -> None:
        self._repo.put(value)

    def __delitem__(self, key: str) -> None:
        self._repo.delete(key)

    def __iter__(self):
        return iter(self._repo.list_keys())

    def __len__(self) -> int:
        return len(self._repo.list_keys())

    def clear(self) -> None:
        self._repo.clear()


class SqliteApprovalRepository:
    def __init__(self, *, sqlite_path: str) -> None:
        self._path = str(sqlite_path).strip()
        if not self._path:
            raise ValueError('sqlite_path is required')
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self.tickets = _ApprovalTicketMap(self)
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[Connection]:
        conn = sqlite3.connect(self._path)
        conn.execute('PRAGMA journal_mode = WAL')
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        plan = SchemaMigrationPlan(component='approval_tickets', target_version=SCHEMA_VERSION, steps=(self._migrate_v1, self._migrate_v2, self._migrate_v3, self._migrate_v4, self._migrate_v5, self._migrate_v6))
        with self._connect() as conn:
            SafetySqliteMigrator().apply(conn, plan)

    @staticmethod
    def _migrate_v1(conn: Connection) -> None:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS safety_approval_tickets (
                action_id TEXT PRIMARY KEY,
                approvals_json TEXT NOT NULL
            )
        ''')

    @staticmethod
    def _migrate_v2(conn: Connection) -> None:
        cols = {str(row[1]) for row in conn.execute('PRAGMA table_info(safety_approval_tickets)').fetchall()}
        if 'state' not in cols:
            conn.execute("ALTER TABLE safety_approval_tickets ADD COLUMN state TEXT NOT NULL DEFAULT 'pending'")
        if 'rejections_json' not in cols:
            conn.execute("ALTER TABLE safety_approval_tickets ADD COLUMN rejections_json TEXT NOT NULL DEFAULT '[]'")
        if 'requested_by' not in cols:
            conn.execute("ALTER TABLE safety_approval_tickets ADD COLUMN requested_by TEXT NOT NULL DEFAULT ''")
        if 'expires_at' not in cols:
            conn.execute("ALTER TABLE safety_approval_tickets ADD COLUMN expires_at TEXT NOT NULL DEFAULT ''")

    @staticmethod
    def _migrate_v3(conn: Connection) -> None:
        cols = {str(row[1]) for row in conn.execute('PRAGMA table_info(safety_approval_tickets)').fetchall()}
        if 'required_approvals' not in cols:
            conn.execute("ALTER TABLE safety_approval_tickets ADD COLUMN required_approvals INTEGER NOT NULL DEFAULT 0")
        if 'escalation_level' not in cols:
            conn.execute("ALTER TABLE safety_approval_tickets ADD COLUMN escalation_level INTEGER NOT NULL DEFAULT 0")

    @staticmethod
    def _migrate_v4(conn: Connection) -> None:
        cols = {str(row[1]) for row in conn.execute('PRAGMA table_info(safety_approval_tickets)').fetchall()}
        if 'requested_by' not in cols:
            conn.execute("ALTER TABLE safety_approval_tickets ADD COLUMN requested_by TEXT NOT NULL DEFAULT ''")

    @staticmethod
    def _migrate_v5(conn: Connection) -> None:
        cols = {str(row[1]) for row in conn.execute('PRAGMA table_info(safety_approval_tickets)').fetchall()}
        if 'version' not in cols:
            conn.execute("ALTER TABLE safety_approval_tickets ADD COLUMN version INTEGER NOT NULL DEFAULT 0")
        if 'lease_owner' not in cols:
            conn.execute("ALTER TABLE safety_approval_tickets ADD COLUMN lease_owner TEXT NOT NULL DEFAULT ''")

    @staticmethod
    def _migrate_v6(conn: Connection) -> None:
        cols = {str(row[1]) for row in conn.execute('PRAGMA table_info(safety_approval_tickets)').fetchall()}
        if 'fencing_token' not in cols:
            conn.execute("ALTER TABLE safety_approval_tickets ADD COLUMN fencing_token INTEGER NOT NULL DEFAULT 0")

    def get(self, action_id: str) -> ApprovalTicket:
        action_key = str(action_id).strip()
        if not action_key:
            raise ValueError('action_id is required')
        with self._connect() as conn:
            row = conn.execute(
                'SELECT approvals_json, state, rejections_json, requested_by, expires_at, required_approvals, escalation_level, version, lease_owner, fencing_token FROM safety_approval_tickets WHERE action_id = ?',
                (action_key,),
            ).fetchone()
        if row is None:
            return ApprovalTicket(action_id=action_key)
        approvals = tuple(str(item) for item in json.loads(str(row[0]) or '[]'))
        try:
            state = ApprovalWorkflowState(str(row[1] or ApprovalWorkflowState.PENDING.value))
        except Exception:
            state = ApprovalWorkflowState.PENDING
        rejections = tuple(str(item) for item in json.loads(str(row[2]) or '[]'))
        return ApprovalTicket(
            action_id=action_key,
            approvals=approvals,
            state=state,
            rejections=rejections,
            requested_by=str(row[3] or ''),
            expires_at=str(row[4] or ''),
            required_approvals=int(row[5] or 0),
            escalation_level=int(row[6] or 0),
            version=int(row[7] or 0),
            lease_owner=str(row[8] or ''),
            fencing_token=int(row[9] or 0),
        )

    def put(self, ticket: ApprovalTicket) -> None:
        self._put_ticket(ticket, expected_version=None)

    def compare_and_set(self, *, expected_version: int, ticket: ApprovalTicket) -> ApprovalTicket:
        return self._put_ticket(ticket, expected_version=int(expected_version))

    def acquire_lease(self, *, action_id: str, owner: str) -> ApprovalTicket:
        current = self.get(action_id)
        leased = ApprovalTicket(**{**current.__dict__, 'lease_owner': str(owner), 'version': int(current.version) + 1, 'fencing_token': int(current.fencing_token) + 1})
        return self._put_ticket(leased, expected_version=int(current.version))

    def _put_ticket(self, ticket: ApprovalTicket, expected_version: int | None) -> ApprovalTicket:
        action_key = str(ticket.action_id).strip()
        if not action_key:
            raise ValueError('action_id is required')
        approvals = tuple(str(item).strip() for item in ticket.approvals if str(item).strip())
        rejections = tuple(str(item).strip() for item in ticket.rejections if str(item).strip())
        base_version = int(ticket.version or 0)
        next_version = int(expected_version + 1) if expected_version is not None else max(1, base_version)
        next_fencing_token = int(ticket.fencing_token or 0)
        current = self.get(action_key)
        if expected_version is not None:
            if current.lease_owner and ticket.lease_owner and current.lease_owner != ticket.lease_owner and int(ticket.fencing_token or 0) < int(current.fencing_token or 0):
                raise RuntimeError('approval_ticket_stale_fencing_token')
            next_fencing_token = max(next_fencing_token, int(current.fencing_token or 0))
        values = (
            action_key,
            json.dumps(approvals),
            str(ticket.state.value),
            json.dumps(rejections),
            str(ticket.requested_by or ''),
            str(ticket.expires_at or ''),
            int(ticket.required_approvals or 0),
            int(ticket.escalation_level or 0),
            next_version,
            str(ticket.lease_owner or ''),
            next_fencing_token,
        )
        with self._connect() as conn:
            if expected_version is None:
                conn.execute(
                    '''
                    INSERT INTO safety_approval_tickets(action_id, approvals_json, state, rejections_json, requested_by, expires_at, required_approvals, escalation_level, version, lease_owner, fencing_token)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(action_id) DO UPDATE SET approvals_json = excluded.approvals_json, state = excluded.state, rejections_json = excluded.rejections_json, requested_by = excluded.requested_by, expires_at = excluded.expires_at, required_approvals = excluded.required_approvals, escalation_level = excluded.escalation_level, version = excluded.version, lease_owner = excluded.lease_owner, fencing_token = excluded.fencing_token
                    ''',
                    values,
                )
            else:
                existing = conn.execute('SELECT version FROM safety_approval_tickets WHERE action_id = ?', (action_key,)).fetchone()
                if existing is None:
                    if int(expected_version) != 0:
                        raise RuntimeError('approval_ticket_version_conflict')
                    conn.execute(
                        '''
                        INSERT INTO safety_approval_tickets(action_id, approvals_json, state, rejections_json, requested_by, expires_at, required_approvals, escalation_level, version, lease_owner, fencing_token)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''',
                        values,
                    )
                else:
                    updated = conn.execute(
                        '''
                        UPDATE safety_approval_tickets SET approvals_json = ?, state = ?, rejections_json = ?, requested_by = ?, expires_at = ?, required_approvals = ?, escalation_level = ?, version = ?, lease_owner = ?, fencing_token = ? WHERE action_id = ? AND version = ?
                        ''',
                        (json.dumps(approvals), str(ticket.state.value), json.dumps(rejections), str(ticket.requested_by or ''), str(ticket.expires_at or ''), int(ticket.required_approvals or 0), int(ticket.escalation_level or 0), next_version, str(ticket.lease_owner or ''), next_fencing_token, action_key, int(expected_version)),
                    ).rowcount
                    if updated == 0:
                        raise RuntimeError('approval_ticket_version_conflict')
        return ApprovalTicket(**{**ticket.__dict__, 'version': next_version, 'fencing_token': next_fencing_token})

    def record_approval(self, *, action_id: str, approver: str) -> ApprovalTicket:
        current = self.get(action_id)
        approvals = tuple(dict.fromkeys([*current.approvals, str(approver).strip()]))
        required = max(int(current.required_approvals or 0), 2)
        state = current.state if current.state is ApprovalWorkflowState.REJECTED else (ApprovalWorkflowState.APPROVED if len(approvals) >= required else ApprovalWorkflowState.PARTIALLY_APPROVED)
        return self.compare_and_set(
            expected_version=int(current.version),
            ticket=ApprovalTicket(
                action_id=current.action_id,
                approvals=approvals,
                state=state,
                rejections=current.rejections,
                requested_by=current.requested_by,
                expires_at=current.expires_at,
                required_approvals=required,
                escalation_level=current.escalation_level,
                version=current.version,
                lease_owner=current.lease_owner,
                fencing_token=current.fencing_token,
            ),
        )

    def record_rejection(self, *, action_id: str, approver: str) -> ApprovalTicket:
        current = self.get(action_id)
        rejections = tuple(dict.fromkeys([*current.rejections, str(approver).strip()]))
        return self.compare_and_set(
            expected_version=int(current.version),
            ticket=ApprovalTicket(
                action_id=current.action_id,
                approvals=current.approvals,
                state=ApprovalWorkflowState.REJECTED,
                rejections=rejections,
                requested_by=current.requested_by,
                expires_at=current.expires_at,
                required_approvals=current.required_approvals,
                escalation_level=current.escalation_level,
                version=current.version,
                lease_owner=current.lease_owner,
                fencing_token=current.fencing_token,
            ),
        )

    def mark_executed(self, *, action_id: str) -> ApprovalTicket:
        current = self.get(action_id)
        return self.compare_and_set(
            expected_version=int(current.version),
            ticket=ApprovalTicket(
                action_id=current.action_id,
                approvals=current.approvals,
                state=ApprovalWorkflowState.EXECUTED,
                rejections=current.rejections,
                requested_by=current.requested_by,
                expires_at=current.expires_at,
                required_approvals=current.required_approvals,
                escalation_level=current.escalation_level,
                version=current.version,
                lease_owner=current.lease_owner,
                fencing_token=current.fencing_token,
            ),
        )

    def delete(self, key: str) -> None:
        with self._connect() as conn:
            conn.execute('DELETE FROM safety_approval_tickets WHERE action_id = ?', (str(key).strip(),))

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute('DELETE FROM safety_approval_tickets')

    def list_keys(self) -> tuple[str, ...]:
        with self._connect() as conn:
            rows = conn.execute('SELECT action_id FROM safety_approval_tickets ORDER BY action_id ASC').fetchall()
        return tuple(str(row[0]) for row in rows)


__all__ = ['CANON_SAFETY_APPROVAL_REPOSITORY', 'SCHEMA_VERSION', 'ApprovalRepository', 'InMemoryApprovalRepository', 'SqliteApprovalRepository']
