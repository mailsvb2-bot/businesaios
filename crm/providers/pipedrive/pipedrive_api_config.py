from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PipedriveApiConfig:
    api_base_template: str = 'https://{company_domain}.pipedrive.com/api/v2'
    oauth_base_url: str = 'https://oauth.pipedrive.com'
    timeout_seconds: float = 20.0
