from __future__ import annotations

from interfaces.messaging._shared.runner_base import RunnerBase
from interfaces.web.chat_widget.delivery_mapper import map_result
from interfaces.web.chat_widget.outbound_sender import send_raw
from interfaces.web.chat_widget.runner_components import build_config


class Runner(RunnerBase):
    def __init__(self):
        super().__init__(build_config=build_config, send_raw=send_raw, map_result=map_result)
