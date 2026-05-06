"""Canonical collapse principles (hard invariants).

1) Collapse must reduce project size (files/lines/artifacts).
2) No loss of semantic functionality (including formulas and unique logic).
"""

CANON_COLLAPSE_PRINCIPLES = {
    "must_reduce_project_size": True,
    "no_functional_regression": True,
    "preserve_all_semantics": True,
    "preserve_all_formulas": True,
}
