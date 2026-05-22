from fastapi.testclient import TestClient

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
