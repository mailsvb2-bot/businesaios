from __future__ import annotations

from economics.contracts import TruthFragment

CANON_RUNTIME_ECONOMIC_CORE_ASSEMBLER = True


def assemble_truth_fragments(*fragments: TruthFragment | None) -> tuple[TruthFragment, ...]:
    return tuple(fragment for fragment in fragments if fragment is not None)
