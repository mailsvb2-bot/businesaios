from __future__ import annotations

import os
import sys
import traceback
from collections.abc import Sequence


def run(argv: Sequence[str]) -> int:
    """Run pytest under coverage and persist data before hard process exit.

    Some runtime imports register interpreter-shutdown hooks that can keep a
    coverage shard alive after pytest has already returned. The ordinary pytest
    CI helper avoids that problem with ``os._exit``; coverage shards need the
    same boundary, but only after coverage has been stopped and saved.
    """

    from coverage import Coverage
    import pytest

    coverage = Coverage(branch=True, source=["."], data_suffix=True)
    exit_code = 1
    coverage.start()
    try:
        exit_code = int(pytest.main(list(argv)))
    except BaseException:  # pragma: no cover - defensive CI boundary
        traceback.print_exc()
        exit_code = 1
    finally:
        try:
            coverage.stop()
            coverage.save()
        except BaseException:  # pragma: no cover - defensive CI boundary
            traceback.print_exc()
            exit_code = 1
    return exit_code


def main() -> int:
    return run(sys.argv[1:])


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)


__all__ = ["main", "run"]
