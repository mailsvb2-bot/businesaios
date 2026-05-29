from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

Json = dict[str, Any]


@dataclass(frozen=True)
class CreativeRotation:
    enable: list[str]
    pause: list[str]
    notes: str = ""


class CreativeRotator:
    """Rotate creatives based on simple fatigue signals.

    If ctr drops below threshold -> pause creative.
    """

    def rotate(self, creatives: list[Json], *, min_ctr_x10000: int = 50) -> CreativeRotation:
        enable: list[str] = []
        pause: list[str] = []
        thr = int(min_ctr_x10000 or 0)
        for c in creatives or []:
            cid = str(c.get("id") or c.get("creative_id") or "")
            if not cid:
                continue
            ctr = int(_get_int(c, ["ctr_x10000", "ctr"], default=0))
            if thr > 0 and ctr > 0 and ctr < thr:
                pause.append(cid)
            else:
                enable.append(cid)
        return CreativeRotation(enable=enable, pause=pause, notes="ok")


def _get_int(d: Json, keys: list[str], *, default: int = 0) -> int:
    for k in keys:
        v = d.get(k)
        if v is None:
            continue
        try:
            return int(v)
        except Exception:
            continue
    return int(default)
