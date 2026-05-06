from __future__ import annotations


class StaticOriginIngestor:
    ORIGIN = ''
    IS_STUB = True

    def ingest(self, payload: dict[str, object]) -> dict[str, object]:
        event = dict(payload)
        event.setdefault('origin', self.ORIGIN)
        event.setdefault('channel', self.ORIGIN)
        event.setdefault('source_stub', self.IS_STUB)
        return event
