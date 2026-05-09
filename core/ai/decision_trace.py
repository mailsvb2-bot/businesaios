from __future__ import annotations

import sys

from core.decision import ai_decision_trace as _canonical

sys.modules[__name__] = _canonical
