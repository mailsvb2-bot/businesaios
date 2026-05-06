from __future__ import annotations

import hashlib
import time

from contracts.demand import ClientRequest
from shared.numbers import coerce_int


class RequestParser:
    def _stable_request_id(self, *, event: dict[str, object], text: str) -> str:
        explicit = str(event.get('request_id') or event.get('lead_id') or '').strip()
        if explicit:
            return explicit
        session_hint = str(event.get('session_id') or event.get('conversation_id') or '')
        created_hint = str(event.get('created_at_ms') or '')
        seed = '|'.join((
            str(event.get('customer_id') or 'anonymous'),
            str(event.get('channel') or event.get('origin') or 'unknown'),
            session_hint,
            created_hint,
            text,
        ))
        return f"req-{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:16]}"

    def parse(self, event: dict[str, object]) -> ClientRequest:
        text = str(event.get('text') or event.get('message') or '').strip()
        return ClientRequest(
            request_id=self._stable_request_id(event=event, text=text),
            text=text,
            channel=str(event.get('channel') or event.get('origin') or 'unknown'),
            created_at_ms=coerce_int(event.get('created_at_ms'), int(time.time() * 1000), minimum=0),
            customer_id=str(event.get('customer_id') or event.get('contact_id') or 'anonymous'),
            session_id=str(event.get('session_id') or event.get('customer_id') or 'session-anon'),
            location_hint=str(event.get('location_hint') or ''),
            budget_hint=str(event.get('budget_hint') or ''),
            urgency_hint=str(event.get('urgency_hint') or ''),
            metadata={k: v for k, v in event.items() if k not in {'text', 'message'}},
        )
