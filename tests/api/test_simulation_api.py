from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app


def test_simulation_api_runs_mock_closed_loop() -> None:
    client = TestClient(app)

    response = client.post(
        "/simulations/run",
        json={
            "spec": {
                "spec_id": "spec_sim_1",
                "instruction_id": "instr_sim_1",
                "version": "v2",
                "task_goal": "确认收货时间",
                "role_definition": "你是站长",
                "opening_requirements": ["您好，请问是张先生吗？"],
                "flow_steps": [
                    {
                        "step_id": "step_1",
                        "order": 1,
                        "title": "身份确认",
                        "raw_text": "确认身份",
                    },
                    {
                        "step_id": "step_2",
                        "order": 2,
                        "title": "确认配送时间",
                        "raw_text": "确认收货时间",
                    },
                ],
                "faq_items": [],
                "constraint_items": [],
                "fallback_policy": [],
                "required_steps": [
                    {
                        "id": "identity_check",
                        "name": "确认身份",
                        "order": 0,
                        "required": True,
                        "evidence_requirement": "您好，请问是张先生吗？",
                    }
                ],
                "required_slots": [
                    {
                        "name": "delivery_time",
                        "required": True,
                        "accepted_values": ["今天", "明天", "下午"],
                    }
                ],
                "forbidden_actions": [],
                "completion_conditions": ["完成关键流程步骤", "符合结束要求"],
                "hard_fail_conditions": [],
                "soft_dimensions": [
                    {
                        "id": "task_focus",
                        "name": "任务聚焦度",
                        "weight": 1.0,
                        "rubric": ["保持任务推进"],
                    }
                ],
            },
            "task_instruction_text": "请先确认用户身份，再确认收货时间。",
            "adapter": {"type": "mock"},
            "simulation": {
                "profile_id": "cooperative",
                "primary_branch": "cooperative",
                "max_turns": 6,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["profile_id"] == "cooperative"
    assert body["termination_reason"] in {"task_complete", "max_turns"}
    assert "evaluation" in body


def test_simulation_api_accepts_http_adapter_credentials() -> None:
    client = TestClient(app)

    class _FakeResult:
        def model_dump(self):
            return {
                "simulation_id": "sim_http",
                "profile_id": "cooperative",
                "termination_reason": "task_complete",
                "evaluation": {},
            }

    with patch("app.api.routes_simulation.ConversationRunner.run_http", new_callable=AsyncMock) as mock_run_http:
        mock_run_http.return_value = _FakeResult()

        response = client.post(
            "/simulations/run",
            json={
                "spec": {
                    "spec_id": "spec_http",
                    "instruction_id": "instr_http",
                    "version": "v2",
                    "task_goal": "确认收货时间",
                    "required_steps": [],
                    "required_slots": [],
                    "soft_dimensions": [],
                },
                "task_instruction_text": "请确认用户身份，再确认收货时间。",
                "adapter": {
                    "type": "http",
                    "endpoint": "https://hotaruapi.com/v1",
                    "api_key": "secret-key",
                    "model": "gpt-4o-mini",
                    "auth_type": "bearer",
                },
                "simulation": {
                    "profile_id": "cooperative",
                    "primary_branch": "cooperative",
                    "max_turns": 2,
                },
            },
        )

    assert response.status_code == 200
    mock_run_http.assert_awaited_once()
    kwargs = mock_run_http.await_args.kwargs
    assert kwargs["endpoint"] == "https://hotaruapi.com/v1"
    assert kwargs["api_key"] == "secret-key"
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["auth_type"] == "bearer"


def test_check_model_endpoint_returns_probe_result() -> None:
    client = TestClient(app)

    response = client.post(
        "/simulations/check-model",
        json={
            "name": "mimo",
            "api_url": "https://hotaruapi.com/v1",
            "api_key": "test-key",
            "model": "gpt-4o-mini",
            "protocol_mode": "auto",
            "auth_type": "bearer",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "ok" in body
    assert "protocol_type" in body
    assert "reply_preview" in body


def test_list_models_endpoint_returns_model_names() -> None:
    client = TestClient(app)

    response = client.post(
        "/simulations/list-models",
        json={
            "api_url": "https://hotaruapi.com/v1",
            "api_key": "test-key",
            "auth_type": "bearer",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "ok" in body
    assert "models" in body
