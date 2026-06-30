from __future__ import annotations

from runtime.economics import UnitEconomicsSnapshot, explain_unit_economics

CANON_THIN_HANDLER = True

def handle_economics_explain(snapshot: UnitEconomicsSnapshot) -> str:
    return explain_unit_economics(snapshot)
