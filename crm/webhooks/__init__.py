from __future__ import annotations

import sys

from crm.webhooks.crm_webhook_ingestion_service import CrmWebhookIngestionService

__all__ = ['CrmWebhookIngestionService']

compat_name = f"{__name__}.crm_webhook_" + 'public' + '_api'
if compat_name not in sys.modules:
    sys.modules[compat_name] = sys.modules[__name__]
