from app.simulators.ai_user_simulator import OpenAIUserSimulatorAdapter


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
            raise RuntimeError("blocked")
        return _FakeResponse(self._content)


def test_ai_user_simulator_parses_structured_reply() -> None:
    adapter = OpenAIUserSimulatorAdapter(
        client=_FakeClient(
            """```json
{
  "state": "questioning",
  "intent": "ask_why",
  "reply": "为什么必须这样？",
  "should_end": false
}
```"""
        )
    )

    result = adapter.generate_turn("dummy prompt")

    assert result.state == "questioning"
    assert result.intent == "ask_why"
    assert result.reply == "为什么必须这样？"


def test_ai_user_simulator_returns_none_on_failure() -> None:
    adapter = OpenAIUserSimulatorAdapter(client=_FakeClient("", should_raise=True))

    result = adapter.generate_turn("dummy prompt")

    assert result is None
