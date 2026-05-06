from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ServicePage:
    page_id: str = ''
    service_name: str = ''
    url: str = ''
