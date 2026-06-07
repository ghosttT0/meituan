import pytest

from app.domain.conversation import Conversation, Turn
from app.domain.eval_spec import EvalSpec, SoftDimension
from app.domain.evaluation_result import RuleResult
from app.evaluators.judge.panel_judge import PanelJudge


def build_spec() -> EvalSpec:
    return EvalSpec(
        spec_id="spec_panel",
        instruction_id="instr_panel",
        version="v1",
        task_goal="确认收货时间并尽量快速说明重点",
        soft_dimensions=[
            SoftDimension(
                id="task_focus",
                name="任务聚焦度",
                weight=1.0,
                rubric=["是否持续围绕任务目标推进"],
            )
        ],
    )


def build_conversation() -> Conversation:
    return Conversation(
        conversation_id="conv_panel",
        instruction_id="instr_panel",
        metadata={"scenario_key": "busy_interrupt"},
        turns=[
            Turn(turn_id=1, speaker="user", text="我现在有点忙，你快点说重点。"),
            Turn(turn_id=2, speaker="agent", text="好的，我只确认一个收货时间，今天下午方便吗？"),
        ],
    )


class _StablePanelAdapter:
    def score_dimension(self, dimension_id: str, rubric: list[str], conversation_text: str, judge_role: str = "general") -> dict:
        mapping = {
            ("task_alignment", "task_focus"): 0.72,
            ("experience_risk", "task_focus"): 0.66,
        }
        score = mapping[(judge_role, dimension_id)]
        return {
            "dimension_id": dimension_id,
            "score": score,
            "confidence": 0.82,
            "reason": f"{judge_role}:{dimension_id}",
            "evidence_turn_ids": [2],
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
            "passed": True,
            "confidence": 0.8,
            "reason": f"{judge_role}:{rule_id}",
            "evidence_turn_ids": [2],
            "status": "ok",
        }


class _ArbitratingPanelAdapter:
    def score_dimension(self, dimension_id: str, rubric: list[str], conversation_text: str, judge_role: str = "general") -> dict:
        mapping = {
            ("task_alignment", "task_focus"): 0.92,
            ("experience_risk", "task_focus"): 0.48,
            ("arbitrator", "task_focus"): 0.74,
        }
        score = mapping[(judge_role, dimension_id)]
        return {
            "dimension_id": dimension_id,
            "score": score,
            "confidence": 0.86,
            "reason": f"{judge_role}:{dimension_id}",
            "evidence_turn_ids": [2],
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
        mapping = {
            ("task_alignment", "scenario_busy_focus"): True,
            ("experience_risk", "scenario_busy_focus"): False,
            ("arbitrator", "scenario_busy_focus"): True,
        }
        return {
            "rule_id": rule_id,
            "passed": mapping[(judge_role, rule_id)],
            "confidence": 0.84,
            "reason": f"{judge_role}:{rule_id}",
            "evidence_turn_ids": [2],
            "status": "ok",
        }


class _PartialFailurePanelAdapter:
    def score_dimension(self, dimension_id: str, rubric: list[str], conversation_text: str, judge_role: str = "general") -> dict:
        if judge_role == "task_alignment":
            return {
                "dimension_id": dimension_id,
                "score": 0.7,
                "confidence": 0.78,
                "reason": "judge_a: 解释基础到位，但细节不足",
                "evidence_turn_ids": [2],
                "status": "ok",
            }
        return {
            "dimension_id": dimension_id,
            "score": 0.5,
            "confidence": 0.3,
            "reason": "LLM评估失败：模型未返回内容",
            "evidence_turn_ids": [],
            "status": "fallback",
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
            "evidence_turn_ids": [2] if baseline_passed else [],
            "status": "ok",
        }


def test_panel_judge_averages_primary_judges_when_gap_is_small() -> None:
    panel = PanelJudge(adapter=_StablePanelAdapter())

    result = panel.evaluate(
        build_spec(),
        build_conversation(),
        [
            RuleResult(
                rule_id="scenario_busy_focus",
                passed=True,
                score_delta=1.0,
                weight=1.8,
                evidence_turn_ids=[2],
                reason="忙碌打断场景已快速聚焦",
            )
        ],
    )

    assert len(result.panel_results) == 2
    assert result.arbitration_records == []
    assert result.final_judge_results[0].dimension_id == "task_focus"
    assert result.final_judge_results[0].score == pytest.approx(0.69)
    assert result.final_rule_results[0].rule_id == "scenario_busy_focus"
    assert result.final_rule_results[0].passed is True


def test_panel_judge_uses_arbitrator_for_large_dimension_gap() -> None:
    panel = PanelJudge(adapter=_ArbitratingPanelAdapter())

    result = panel.evaluate(build_spec(), build_conversation(), [])

    assert len(result.panel_results) == 3
    assert len(result.arbitration_records) == 1
    assert result.arbitration_records[0].target_type == "dimension"
    assert result.arbitration_records[0].target_id == "task_focus"
    assert result.final_judge_results[0].score == pytest.approx(0.74)
    assert result.final_judge_results[0].is_arbitration is True


def test_panel_judge_arbitrates_subjective_scenario_rules() -> None:
    panel = PanelJudge(adapter=_ArbitratingPanelAdapter())

    result = panel.evaluate(
        build_spec(),
        build_conversation(),
        [
            RuleResult(
                rule_id="scenario_busy_focus",
                passed=True,
                score_delta=1.0,
                weight=1.8,
                evidence_turn_ids=[2],
                reason="忙碌打断场景已快速聚焦",
            )
        ],
    )

    scenario_record = next(item for item in result.arbitration_records if item.target_type == "scenario_rule")
    assert scenario_record.target_id == "scenario_busy_focus"
    assert result.final_rule_results[0].passed is True
    assert result.final_rule_results[0].review_source == "judge_c"


def test_panel_judge_supports_single_judge_mode() -> None:
    panel = PanelJudge(adapter=_StablePanelAdapter())

    result = panel.evaluate(
        build_spec(),
        build_conversation(),
        [],
        primary_judge_count=1,
        arbitration_enabled=False,
    )

    assert len(result.panel_results) == 1
    assert result.final_judge_results[0].judge_id == "judge_a"
    assert result.final_judge_results[0].score == pytest.approx(0.72)
    assert result.arbitration_records == []


def test_panel_judge_supports_dual_mode_without_arbitration() -> None:
    panel = PanelJudge(adapter=_ArbitratingPanelAdapter())

    result = panel.evaluate(
        build_spec(),
        build_conversation(),
        [
            RuleResult(
                rule_id="scenario_busy_focus",
                passed=True,
                score_delta=1.0,
                weight=1.8,
                evidence_turn_ids=[2],
                reason="忙碌打断场景已快速聚焦",
            )
        ],
        primary_judge_count=2,
        arbitration_enabled=False,
    )

    assert len(result.panel_results) == 2
    assert result.arbitration_records == []
    assert result.final_judge_results[0].judge_id == "panel_average"
    assert result.final_judge_results[0].score == pytest.approx(0.70)
    assert result.final_rule_results[0].review_source == "rule_engine_fallback"
    assert result.final_rule_results[0].status == "needs_review"


def test_panel_judge_ignores_failed_reviewer_in_final_dimension_score() -> None:
    panel = PanelJudge(adapter=_PartialFailurePanelAdapter())

    result = panel.evaluate(
        build_spec(),
        build_conversation(),
        [],
        primary_judge_count=2,
        arbitration_enabled=True,
    )

    assert result.final_judge_results[0].score == pytest.approx(0.70)
    assert "judge_a" in result.final_judge_results[0].reason
    assert "judge_b" in result.final_judge_results[0].reason
