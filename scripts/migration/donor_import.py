"""Import a ClientPlatform SQLite database into BusinessAIOS flow facts.

    python -m scripts.migration.donor_import --donor clientplatform.db --business-id B --tenant T --owner-user-id U
        (dry-run: prints what would be imported, writes nothing)
    ... --apply --events-db runtime/data/<tenant>/events.db
        (appends missing facts; re-running is a no-op)

The donor database is opened read-only (``mode=ro``).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from typing import Any

from application.business_flows import donor_import as ci
from contracts.event_store import append_event_strict
from runtime.platform.donor_db_reader import read_donor


def run(args: argparse.Namespace, *, store: Any = None) -> dict[str, Any]:
    rows = read_donor(args.donor, args.business_id)
    facts, skipped = ci.build_facts(rows, owner_user_id=args.owner_user_id)
    refs = (
        ci.existing_refs(store.iter_events, tenant_id=args.tenant, event_types=[f.event_type for f in facts])
        if store
        else set()
    )
    todo = ci.plan(facts, refs)
    report = {
        "mode": "apply" if args.apply else "dry-run",
        "donor_rows": {t: len(v) for t, v in rows.items()},
        "facts_total": len(facts),
        "already_imported": len(facts) - len(todo),
        "to_import": dict(Counter(f"{f.event_type}:{f.payload.get('step', 'role')}" for f in todo)),
        "skipped": skipped,
    }
    if args.apply:
        if store is None:
            raise SystemExit("--apply requires --events-db")
        for f in todo:
            append_event_strict(store, tenant_id=args.tenant, event=ci.to_event(f, tenant_id=args.tenant))
        report["written"] = len(todo)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--donor", required=True)
    ap.add_argument("--business-id", required=True)
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--owner-user-id", required=True)
    ap.add_argument("--events-db", default="")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    if args.events_db:
        from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

        with SqliteEventStore(args.events_db) as store:
            report = run(args, store=store)
    else:
        report = run(args)
    json.dump(report, sys.stdout, ensure_ascii=False, indent=1)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
