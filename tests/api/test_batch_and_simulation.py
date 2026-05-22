from fastapi.testclient import TestClient

from app.main import app


def test_batch_evaluation_returns_multiple_results() -> None:
    client = TestClient(app)
    payload = {
        "items": [
            {
                "spec": {
                    "spec_id": "spec_batch",
                    "instruction_id": "instr_batch",
                    "version": "v1",
                    "task_goal": "确认时间",
                    "required_steps": [],
                    "required_slots": [],
                    "soft_dimensions": [],
                },
                "conversation": {
                    "conversation_id": "conv_batch_1",
                    "instruction_id": "instr_batch",
                    "turns": [{"turn_id": 1, "speaker": "agent", "text": "您好"}],
                },
            },
            {
                "spec": {
                    "spec_id": "spec_batch",
                    "instruction_id": "instr_batch",
                    "version": "v1",
                    "task_goal": "确认时间",
                    "required_steps": [],
                    "required_slots": [],
                    "soft_dimensions": [],
                },
                "conversation": {
                    "conversation_id": "conv_batch_2",
                    "instruction_id": "instr_batch",
                    "turns": [{"turn_id": 1, "speaker": "agent", "text": "您好"}],
                },
            },
        ]
    }

    response = client.post("/evaluations/batch", json=payload)

    assert response.status_code == 200
    assert len(response.json()["results"]) == 2


def test_simulation_endpoint_is_reserved_but_not_implemented() -> None:
    client = TestClient(app)

    response = client.post(
        "/simulations/run", json={"spec_id": "spec_demo", "model_config": {"name": "stub"}}
    )

    assert response.status_code == 501
    assert response.json()["detail"] == "simulation runner not implemented in prototype"
