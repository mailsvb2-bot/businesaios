from __future__ import annotations

from interfaces.messaging._shared.adapter_base import AdapterBase
from interfaces.web.chat_widget.runner import Runner


class Adapter(AdapterBase):
    def __init__(self):
        super().__init__(runner=Runner())
