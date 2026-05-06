from __future__ import annotations

from demand_capture.demand_event_ingestion import DemandEventIngestion
from demand_capture.request_parser import RequestParser
from demand_capture.request_normalizer import RequestNormalizer
from demand_capture.request_deduplicator import RequestDeduplicator
from demand_capture.request_enricher import RequestEnricher
from demand_capture.origin_tracker import OriginTracker
from demand_capture.channel_origin_mapper import ChannelOriginMapper
from demand_capture.session_linker import SessionLinker
from demand_capture.contact_extractor import ContactExtractor
from demand_capture.geo_extractor import GeoExtractor
from demand_capture.time_window_extractor import TimeWindowExtractor

class DemandCaptureService:
    def __init__(self) -> None:
        self._ingestion = DemandEventIngestion()
        self._parser = RequestParser()
        self._normalizer = RequestNormalizer()
        self._dedup = RequestDeduplicator()
        self._enricher = RequestEnricher()
        self._origin = OriginTracker()
        self._origin_mapper = ChannelOriginMapper()
        self._session = SessionLinker()
        self._contact = ContactExtractor()
        self._geo = GeoExtractor()
        self._time_window = TimeWindowExtractor()

    def capture(self, raw_event: dict[str, object]):
        event = self._ingestion.ingest(raw_event)
        event["session_id"] = self._session.link(event)
        parsed = self._parser.parse(event)
        normalized = self._normalizer.normalize(parsed)
        if self._dedup.is_duplicate(normalized.request_id, normalized.created_at_ms):
            raise ValueError(f"duplicate request: {normalized.request_id}")
        origin = self._origin_mapper.map(self._origin.track(event))
        return self._enricher.enrich(
            normalized,
            origin=origin,
            geo=self._geo.extract(event),
            time_window=self._time_window.extract(event),
            contact=self._contact.extract(event),
        )
