from fastapi.testclient import TestClient

from app.main import app


def test_compile_spec_returns_draft_spec() -> None:
    client = TestClient(app)

    response = client.post(
        "/specs/compile",
        json={
            "instruction_id": "instr_delivery_time",
            "name": "确认送达时间",
            "raw_text": "请先确认用户身份，再确认收货时间，不要承诺一定送达。",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["review_status"] == "draft"
    assert data["required_steps"][0]["id"] == "identity_check"


def test_save_and_get_spec() -> None:
    client = TestClient(app)
    spec_payload = {
        "spec_id": "spec_saved",
        "instruction_id": "instr_saved",
        "version": "v1",
        "task_goal": "确认收货时间",
        "required_steps": [],
        "required_slots": [],
        "soft_dimensions": [],
    }

    save_response = client.post("/specs", json=spec_payload)
    get_response = client.get("/specs/spec_saved")

    assert save_response.status_code == 200
    assert get_response.status_code == 200
    assert get_response.json()["spec_id"] == "spec_saved"


def test_compile_spec_returns_enhanced_fields() -> None:
    client = TestClient(app)

    response = client.post(
        "/specs/compile",
        json={
            "instruction_id": "instr_delivery_time",
            "name": "确认送达时间",
            "raw_text": "# Role\n你是骑手站长\n\n# Task\n确认配送\n\n# Opening Line\n您好，请问是张先生吗？\n\n# Call Flow\n1. 确认身份\n2. 确认是否可配送\n\n# Constraints\n- 每次回复控制在约30个字以内。\n- 如被问及超出职责范围的问题，回复：我向同事确认后再回电给你。",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["role_definition"] == "你是骑手站长"
    assert len(data["flow_steps"]) == 2
    assert data["opening_requirements"][0] == "您好，请问是张先生吗？"
    assert data["constraint_items"][0]["category"] == "length_limit"
