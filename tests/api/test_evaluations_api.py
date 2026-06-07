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
    assert len(response.json()["panel_results"]) == 2
    assert "arbitration_records" in response.json()


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


def test_compile_then_evaluate_then_fetch_round_trip() -> None:
    client = TestClient(app)
    compiled = client.post(
        "/specs/compile",
        json={
            "instruction_id": "instr_round_trip",
            "name": "确认送达时间",
            "raw_text": "请先确认身份，再确认收货时间，不要承诺一定送达。",
        },
    ).json()

    result = client.post(
        "/evaluations/run",
        json={
            "spec": compiled,
            "conversation": {
                "conversation_id": "conv_round_trip",
                "instruction_id": "instr_round_trip",
                "turns": [
                    {"turn_id": 1, "speaker": "agent", "text": "您好，请问是张先生吗？"},
                    {"turn_id": 2, "speaker": "user", "text": "是的。"},
                    {"turn_id": 3, "speaker": "agent", "text": "来电是为了确认收货时间，您明天下午方便收货吗？"},
                    {"turn_id": 4, "speaker": "user", "text": "明天下午可以。"},
                    {"turn_id": 5, "speaker": "agent", "text": "好的，感谢您的配合，再见。"},
                ],
            },
        },
    )

    fetched = client.get(f"/evaluations/{result.json()['run_id']}")

    assert result.status_code == 200
    assert fetched.status_code == 200
    assert fetched.json()["conversation_id"] == "conv_round_trip"


def test_run_evaluation_includes_scenario_specific_rules() -> None:
    client = TestClient(app)
    spec = {
        "spec_id": "spec_eval_scenario",
        "instruction_id": "instr_eval_scenario",
        "version": "v2",
        "task_goal": "告知机构客户低延迟直播和标准直播的区别。",
        "faq_items": [
            {"faq_id": "faq_1", "raw_text": "低延迟直播更适合小班课，费用略高。"},
            {"faq_id": "faq_2", "raw_text": "标准直播更适合大班课。"},
        ],
        "required_steps": [],
        "required_slots": [],
        "forbidden_actions": [],
        "soft_dimensions": [],
    }
    conversation = {
        "conversation_id": "conv_eval_scenario",
        "instruction_id": "instr_eval_scenario",
        "metadata": {"scenario_key": "faq_followup"},
        "turns": [
            {"turn_id": 1, "speaker": "user", "text": "低延迟直播和标准直播差在哪？"},
            {"turn_id": 2, "speaker": "agent", "text": "低延迟直播更适合小班课，标准直播更适合大班课。"},
        ],
    }

    response = client.post("/evaluations/run", json={"spec": spec, "conversation": conversation})

    assert response.status_code == 200
    rule_ids = {item["rule_id"] for item in response.json()["rule_results"]}
    assert "scenario_faq_grounding" in rule_ids


def test_run_evaluation_accepts_single_mode() -> None:
    client = TestClient(app)

    response = client.post(
        "/evaluations/run",
        json={
            "evaluation_mode": "single",
            "spec": {
                "spec_id": "spec_single_mode",
                "instruction_id": "instr_single_mode",
                "version": "v1",
                "task_goal": "确认收货时间",
                "required_steps": [],
                "required_slots": [],
                "soft_dimensions": [
                    {
                        "id": "task_focus",
                        "name": "任务聚焦度",
                        "weight": 1.0,
                        "rubric": ["保持任务推进"],
                    }
                ],
            },
            "conversation": {
                "conversation_id": "conv_single_mode",
                "instruction_id": "instr_single_mode",
                "turns": [{"turn_id": 1, "speaker": "agent", "text": "您好，我来确认收货时间"}],
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["evaluation_mode"] == "single"
    assert len(response.json()["panel_results"]) == 1
    assert response.json()["arbitration_records"] == []


def test_run_evaluation_accepts_dual_mode_without_arbitration() -> None:
    client = TestClient(app)

    response = client.post(
        "/evaluations/run",
        json={
            "evaluation_mode": "dual",
            "spec": {
                "spec_id": "spec_dual_mode",
                "instruction_id": "instr_dual_mode",
                "version": "v1",
                "task_goal": "确认收货时间",
                "required_steps": [],
                "required_slots": [],
                "soft_dimensions": [
                    {
                        "id": "task_focus",
                        "name": "任务聚焦度",
                        "weight": 1.0,
                        "rubric": ["保持任务推进"],
                    }
                ],
            },
            "conversation": {
                "conversation_id": "conv_dual_mode",
                "instruction_id": "instr_dual_mode",
                "turns": [{"turn_id": 1, "speaker": "agent", "text": "您好，我来确认收货时间"}],
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["evaluation_mode"] == "dual"
    assert len(response.json()["panel_results"]) == 2
    assert response.json()["arbitration_records"] == []
