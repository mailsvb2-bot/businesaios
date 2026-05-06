from __future__ import annotations


class ChannelRuntimeRunner:
    def __init__(self, *, binding, pipeline) -> None:
        self._binding = binding
        self._pipeline = pipeline

    def accept_inbound(self, raw: dict):
        return self._pipeline.process(self._binding.parse_inbound(raw))
