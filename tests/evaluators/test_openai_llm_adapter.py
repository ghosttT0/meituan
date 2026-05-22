from app.evaluators.judge.llm_adapter import OpenAILLMAdapter


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [type("Choice", (), {"message": type("Msg", (), {"content": content})()})()]


class _FakeClient:
    def __init__(self, content: str, should_raise: bool = False) -> None:
        self._content = content
        self._should_raise = should_raise
        self.chat = type("Chat", (), {"completions": self})()

    def create(self, **kwargs):
        if self._should_raise:
            raise RuntimeError("network down")
        return _FakeResponse(self._content)


def test_openai_adapter_parses_markdown_json_block() -> None:
    adapter = OpenAILLMAdapter(
        client=_FakeClient(
            """```json
{
  "dimension_id": "task_focus",
  "score": 0.82,
  "confidence": 0.74,
  "reason": "说明了来电目的，且持续推进任务。",
  "evidence_turn_ids": [1, 2]
}
```"""
        )
    )

    result = adapter.score_dimension("task_focus", ["保持任务推进"], "agent: 来电是为了确认收货时间")

    assert result["dimension_id"] == "task_focus"
    assert result["score"] == 0.82
    assert result["reason"] == "说明了来电目的，且持续推进任务。"
    assert result["evidence_turn_ids"] == [1, 2]


def test_openai_adapter_returns_chinese_fallback_reason_on_error() -> None:
    adapter = OpenAILLMAdapter(client=_FakeClient("", should_raise=True))

    result = adapter.score_dimension("task_focus", ["保持任务推进"], "agent: 您好")

    assert result["score"] == 0.5
    assert result["confidence"] == 0.3
    assert result["reason"].startswith("LLM评估失败：")
