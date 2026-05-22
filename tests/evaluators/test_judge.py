from app.domain.conversation import Conversation, Turn
from app.domain.eval_spec import EvalSpec, SoftDimension
from app.evaluators.judge.llm_adapter import FakeLLMAdapter
from app.evaluators.judge.rubric_judge import RubricJudge


def test_rubric_judge_returns_structured_scores() -> None:
    conversation = Conversation(
        conversation_id="conv_judge",
        instruction_id="instr_judge",
        turns=[Turn(turn_id=1, speaker="agent", text="来电是为了确认收货时间。")],
    )
    spec = EvalSpec(
        spec_id="spec_judge",
        instruction_id="instr_judge",
        version="v1",
        task_goal="确认收货时间",
        soft_dimensions=[
            SoftDimension(
                id="explanation_quality",
                name="解释充分性",
                weight=1.0,
                rubric=["说明来电目的"],
            )
        ],
    )

    results = RubricJudge(FakeLLMAdapter()).evaluate(spec, conversation)

    assert results[0].dimension_id == "explanation_quality"
    assert 0.0 <= results[0].score <= 1.0
    assert results[0].reason in {"命中评分标准", "未充分命中评分标准"}
