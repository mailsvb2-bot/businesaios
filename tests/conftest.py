from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Tests may run on a server whose shell exports APP_ENV=prod. Keep production
# sqlite fallback fail-closed for real runtime processes, but mark pytest as an
# explicit test-local process so unit storage tests can exercise sqlite contracts.
os.environ["BUSINESAIOS_TEST_RUN"] = "1"
os.environ["BUSINESAIOS_TESTS_CONFTEST_LOADED"] = "1"
os.environ["BUSINESAIOS_ALLOW_TEST_SQLITE_FALLBACK"] = "1"
