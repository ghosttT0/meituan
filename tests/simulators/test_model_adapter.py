import asyncio

from app.simulators.model_adapter import HttpModelAdapter, MockModelAdapter


def test_mock_model_adapter_returns_scripted_reply() -> None:
    adapter = MockModelAdapter()

    asyncio.run(adapter.start_session({}))
    reply = asyncio.run(adapter.send_user_message("您好"))
    asyncio.run(adapter.end_session())

    assert "您好" in reply or "请问" in reply


def test_http_model_adapter_builds_request_payload() -> None:
    adapter = HttpModelAdapter(endpoint="http://localhost/mock")
    payload = adapter.build_payload(
        session_id="session_1", history=[{"speaker": "user", "text": "你好"}]
    )

    assert payload["session_id"] == "session_1"
    assert payload["history"][0]["speaker"] == "user"
