from __future__ import annotations


class ProviderPageGenerator:
    def build(self, business_id: str) -> dict[str, object]:
        return {"slug": f"/providers/{business_id}/", "business_id": business_id}
