from __future__ import annotations

from pathlib import Path

from canon.collapse.import_cycle_detector import build_p0_import_cycle_report

ROOT = Path(__file__).resolve().parents[2]


def test_no_p0_top_level_import_cycles() -> None:
    report = build_p0_import_cycle_report(ROOT)
    assert report.parse_errors == ()
    assert report.p0_cycles == (), "\n\n".join(
        "cycle:\n"
        + "\n".join(f"  {module}" for module in cycle.modules)
        + "\n"
        + "\n".join(f"    {edge}" for edge in cycle.sample_edges)
        for cycle in report.p0_cycles
    )
