from __future__ import annotations

from dataclasses import dataclass

from ..contracts import LLMClient, LLMRequest, LLMResponse, LLMUsage


@dataclass
class MockLLMClient(LLMClient):
    fixed_text: str = "OK"
    raise_error: bool = False

    def generate_sync(self, req: LLMRequest) -> LLMResponse:
        if self.raise_error:
            raise RuntimeError("mock_llm_error")
        usage = LLMUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20)
        return LLMResponse(content=self.fixed_text, finish_reason="stop", usage=usage, raw=None)

    async def generate(self, req: LLMRequest) -> LLMResponse:
        return self.generate_sync(req)
