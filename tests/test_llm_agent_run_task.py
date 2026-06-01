from __future__ import annotations

from core.llm.agent import LLMTaskContext, TaskType
from core.llm.agent.agent import LLMAgent, LLMAgentConfig


class FakeClient:
    def generate_sync(self, req):
        return type(
            "R",
            (),
            {
                "content": "```json\n{\"a\":1}\n```\nOK",
                "finish_reason": "stop",
                "usage": {"total_tokens": 3},
            },
        )()


def test_agent_run_task_extracts_json_and_text():
    agent = LLMAgent(FakeClient(), LLMAgentConfig(default_model="m"))
    ctx = LLMTaskContext(tenant_id="t1", product_id="p1")
    res = agent.run_task(TaskType.OFFER_GENERATE, ctx)
    assert res.json.get("a") == 1
    assert "OK" in res.text
