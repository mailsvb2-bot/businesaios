from __future__ import annotations

import sys

from runtime.observability import telemetry as _canonical

sys.modules[__name__] = _canonical
