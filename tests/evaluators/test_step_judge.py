from unittest.mock import patch

from fastapi.testclient import TestClient

from app.domain.conversation import Conversation, Turn
from app.domain.eval_spec import EvalSpec, RequiredStep, SoftDimension
from app.evaluators.judge.panel_judge import PanelJudge
from app.main import app


def build_step_spec() -> EvalSpec:
    return EvalSpec(
        spec_id="spec_step_judge",
        instruction_id="instr_step_judge",
        version="v1",
        task_goal="通知直播产品升级并确认是否知情",
        required_steps=[
            RequiredStep(
                id="identity_check",
                name="确认身份",
                order=1,
                required=True,
                evidence_requirement="请问您是负责人吗",
            ),
            RequiredStep(
                id="knowledge_check",
                name="确认是否知情",
                order=2,
                required=True,
                evidence_requirement="询问用户是否知道之前已走低延迟线路",
            ),
            RequiredStep(
                id="upgrade_explanation",
                name="传达升级内容",
                order=3,
                required=True,
                evidence_requirement="说明标准直播和低延迟直播的区别及使用方式",
            ),
        ],
        soft_dimensions=[
            SoftDimension(
                id="task_focus",
                name="任务聚焦度",
                weight=1.0,
                rubric=["保持任务推进"],
            )
        ],
    )


def build_step_conversation() -> Conversation:
    return Conversation(
        conversation_id="conv_step_judge",
        instruction_id="instr_step_judge",
        turns=[
            Turn(turn_id=1, speaker="agent", text="您好，请问您是负责人吗？"),
            Turn(turn_id=2, speaker="user", text="是的，我是负责人。"),
            Turn(turn_id=3, speaker="agent", text="您知道之前系统已经为您走低延迟线路吗？"),
            Turn(turn_id=4, speaker="user", text="我之前好像没注意这个选项。"),
            Turn(turn_id=5, speaker="agent", text="标准直播更便宜，低延迟更适合实时互动，之后发布页会分开展示。"),
        ],
    )


class _StepAwareAdapter:
    def score_dimension(self, dimension_id: str, rubric: list[str], conversation_text: str, judge_role: str = "general") -> dict:
        score = 0.86 if judge_role == "task_alignment" else 0.80
        return {
            "dimension_id": dimension_id,
            "score": score,
            "confidence": 0.8,
            "reason": f"{judge_role}:{dimension_id}",
            "evidence_turn_ids": [3, 5],
            "status": "ok",
        }

    def review_scenario(
        self,
        rule_id: str,
        criteria: list[str],
        conversation_text: str,
        baseline_passed: bool,
        baseline_reason: str,
        judge_role: str = "general",
    ) -> dict:
        return {
            "rule_id": rule_id,
            "passed": baseline_passed,
            "confidence": 0.8,
            "reason": baseline_reason,
            "evidence_turn_ids": [],
            "status": "ok",
        }

    def review_required_step(
        self,
        step_id: str,
        step_name: str,
        evidence_requirement: str,
        conversation_text: str,
        candidate_turn_ids: list[int],
        candidate_reason: str,
        judge_role: str = "general",
    ) -> dict:
        completed = {
            "identity_check": True,
            "knowledge_check": True,
            "upgrade_explanation": True,
        }[step_id]
        evidence = {
            "identity_check": [1, 2],
            "knowledge_check": [3, 4],
            "upgrade_explanation": [5],
        }[step_id]
        return {
            "step_id": step_id,
            "step_name": step_name,
            "completed": completed,
            "confidence": 0.88,
            "reason": f"{judge_role}:{step_id}",
            "evidence_turn_ids": evidence,
            "status": "ok",
        }


class _StepReviewAdapter(_StepAwareAdapter):
    def review_required_step(
        self,
        step_id: str,
        step_name: str,
        evidence_requirement: str,
        conversation_text: str,
        candidate_turn_ids: list[int],
        candidate_reason: str,
        judge_role: str = "general",
    ) -> dict:
        if step_id == "knowledge_check":
            return {
                "step_id": step_id,
                "step_name": step_name,
                "completed": False,
                "confidence": 0.62,
                "reason": "候选已召回，但当前证据仍需人工复核",
                "evidence_turn_ids": [3, 4],
                "status": "needs_review",
            }
        return super().review_required_step(
            step_id,
            step_name,
            evidence_requirement,
            conversation_text,
            candidate_turn_ids,
            candidate_reason,
            judge_role,
        )


def test_required_step_candidate_collector_recalls_semantic_candidates() -> None:
    from app.evaluators.rules.step_candidates import RequiredStepCandidateCollector

    candidates = RequiredStepCandidateCollector().collect(build_step_spec(), build_step_conversation())

    by_id = {item.step_id: item for item in candidates}
    assert set(by_id) == {"identity_check", "knowledge_check", "upgrade_explanation"}
    assert 3 in by_id["knowledge_check"].candidate_turn_ids or 4 in by_id["knowledge_check"].candidate_turn_ids
    assert 5 in by_id["upgrade_explanation"].candidate_turn_ids


def test_panel_judge_resolves_required_steps_from_candidates() -> None:
    from app.evaluators.rules.step_candidates import RequiredStepCandidateCollector

    panel = PanelJudge(adapter=_StepAwareAdapter())
    candidates = RequiredStepCandidateCollector().collect(build_step_spec(), build_step_conversation())

    result = panel.evaluate(
        build_step_spec(),
        build_step_conversation(),
        [],
        step_candidates=candidates,
    )

    assert len(result.final_step_results) == 3
    assert all(item.completed for item in result.final_step_results)
    knowledge = next(item for item in result.final_step_results if item.step_id == "knowledge_check")
    assert set(knowledge.evidence_turn_ids) == {3, 4}


def test_evaluation_api_uses_step_judge_instead_of_strict_event_match() -> None:
    client = TestClient(app)

    with patch("app.pipeline.evaluation_runner.EvaluationRunner._build_adapter", return_value=_StepAwareAdapter()):
        response = client.post(
            "/evaluations/run",
            json={
                "spec": build_step_spec().model_dump(),
                "conversation": build_step_conversation().model_dump(),
            },
        )

    assert response.status_code == 200
    body = response.json()
    required_steps_rule = next(item for item in body["rule_results"] if item["rule_id"] == "required_steps")
    assert required_steps_rule["passed"] is True
    assert body["step_results"]
    assert all(item["completed"] for item in body["step_results"])


def test_evaluation_api_labels_candidate_recall_as_review_instead_of_failure() -> None:
    client = TestClient(app)

    with patch("app.pipeline.evaluation_runner.EvaluationRunner._build_adapter", return_value=_StepReviewAdapter()):
        response = client.post(
            "/evaluations/run",
            json={
                "spec": build_step_spec().model_dump(),
                "conversation": build_step_conversation().model_dump(),
            },
        )

    body = response.json()
    required_steps_rule = next(item for item in body["rule_results"] if item["rule_id"] == "required_steps")
    assert required_steps_rule["status"] == "needs_review"
    assert required_steps_rule["score_delta"] > 0.0
    assert "待复核" in required_steps_rule["reason"]
    assert "确认是否知情" in required_steps_rule["reason"]
    assert "?" not in required_steps_rule["reason"]
    assert any(str(item).startswith("[待复核]") for item in body["evaluation_summary"]["key_weaknesses"])
    assert all("?" not in str(item) for item in body["evaluation_summary"]["key_weaknesses"])
