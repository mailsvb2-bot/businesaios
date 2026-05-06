from __future__ import annotations

class SeoPublishPipeline:
    def publish(self, page: dict[str, object]) -> dict[str, object]:
        return {"published": True, **dict(page)}
