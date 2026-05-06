from __future__ import annotations

CANON_THIN_HANDLER = True

from runtime.economics import UnitEconomicsSnapshot, explain_unit_economics


def handle_economics_explain(snapshot: UnitEconomicsSnapshot) -> str:
    return explain_unit_economics(snapshot)
