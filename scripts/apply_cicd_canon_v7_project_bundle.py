from __future__ import annotations

from collections.abc import Iterator

from scripts.ci.canon_bundle_finalize import finalize_bundle
from scripts.ci.canon_bundle_io import write
from scripts.ci.canon_bundle_part_a import BUNDLE_PART as PART_A
from scripts.ci.canon_bundle_part_b import BUNDLE_PART as PART_B
from scripts.ci.canon_bundle_part_c import BUNDLE_PART as PART_C


def _iter_bundle_entries() -> Iterator[tuple[str, str]]:
    yield from PART_A; yield from PART_B; yield from PART_C

def main() -> None:
    for relative_path, content in _iter_bundle_entries(): write(relative_path, content)
    finalize_bundle()
if __name__ == "__main__": main()
