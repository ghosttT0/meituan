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
        session_id="session_1",
        history=[{"speaker": "user", "text": "你好"}],
        task_instruction_text="请先确认用户身份，再确认收货时间。",
    )

    assert payload["session_id"] == "session_1"
    assert payload["history"][0]["speaker"] == "user"
    assert payload["task_instruction"] == "请先确认用户身份，再确认收货时间。"
    assert payload["system_prompt"] == "请先确认用户身份，再确认收货时间。"


def test_http_model_adapter_normalizes_base_url_to_chat_completions() -> None:
    adapter = HttpModelAdapter(endpoint="https://api.deepseek.com/v1")

    assert adapter.request_url == "https://api.deepseek.com/v1/chat/completions"


def test_http_model_adapter_keeps_full_chat_completions_url() -> None:
    adapter = HttpModelAdapter(endpoint="https://api.deepseek.com/v1/chat/completions")

    assert adapter.request_url == "https://api.deepseek.com/v1/chat/completions"
