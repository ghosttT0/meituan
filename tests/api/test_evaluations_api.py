from fastapi.testclient import TestClient

from app.main import app


def test_run_evaluation_returns_scorecard() -> None:
    client = TestClient(app)
    spec = {
        "spec_id": "spec_eval_api",
        "instruction_id": "instr_eval_api",
        "version": "v1",
        "task_goal": "确认收货时间",
        "required_steps": [
            {
                "id": "identity_check",
                "name": "确认身份",
                "order": 1,
                "required": True,
                "evidence_requirement": "身份确认",
            }
        ],
        "required_slots": [
            {"name": "delivery_time", "required": True, "accepted_values": ["今天", "明天"]}
        ],
        "forbidden_actions": [{"id": "forbid_false_promise", "description": "禁止承诺一定送达"}],
        "soft_dimensions": [
            {
                "id": "explanation_quality",
                "name": "解释充分性",
                "weight": 1.0,
                "rubric": ["说明来电目的"],
            }
        ],
    }
    conversation = {
        "conversation_id": "conv_eval_api",
        "instruction_id": "instr_eval_api",
        "turns": [
            {"turn_id": 1, "speaker": "agent", "text": "您好，请问是王女士吗？"},
            {"turn_id": 2, "speaker": "user", "text": "是的。"},
            {"turn_id": 3, "speaker": "agent", "text": "来电是为了确认收货时间，您今天下午在家吗？"},
            {"turn_id": 4, "speaker": "user", "text": "下午三点后可以。"},
            {"turn_id": 5, "speaker": "agent", "text": "好的，感谢您的配合，再见。"},
        ],
    }

    response = client.post("/evaluations/run", json={"spec": spec, "conversation": conversation})

    assert response.status_code == 200
    assert response.json()["overall_score"] >= 80
    assert response.json()["hard_fail"] is False


def test_get_evaluation_run_returns_saved_payload() -> None:
    client = TestClient(app)
    run_response = client.post(
        "/evaluations/run",
        json={
            "spec": {
                "spec_id": "spec_lookup",
                "instruction_id": "instr_lookup",
                "version": "v1",
                "task_goal": "确认时间",
                "required_steps": [],
                "required_slots": [],
                "soft_dimensions": [],
            },
            "conversation": {
                "conversation_id": "conv_lookup",
                "instruction_id": "instr_lookup",
                "turns": [{"turn_id": 1, "speaker": "agent", "text": "您好"}],
            },
        },
    )

    run_id = run_response.json()["run_id"]
    get_response = client.get(f"/evaluations/{run_id}")

    assert get_response.status_code == 200
    assert get_response.json()["run_id"] == run_id
