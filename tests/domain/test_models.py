from app.domain.conversation import Conversation, Turn
from app.domain.eval_spec import EvalSpec, RequiredSlot, RequiredStep, SoftDimension


def test_eval_spec_validates_required_sections() -> None:
    spec = EvalSpec(
        spec_id="spec_demo",
        instruction_id="instr_demo",
        version="v1",
        task_goal="确认收货时间",
        required_steps=[
            RequiredStep(
                id="identity_check",
                name="确认身份",
                order=1,
                required=True,
                evidence_requirement="需要身份确认话术",
            )
        ],
        required_slots=[
            RequiredSlot(name="delivery_time", required=True, accepted_values=["今天", "明天"])
        ],
        soft_dimensions=[
            SoftDimension(
                id="explanation_quality",
                name="解释充分性",
                weight=0.3,
                rubric=["说明来电原因", "说明追问原因"],
            )
        ],
    )

    assert spec.spec_id == "spec_demo"
    assert spec.required_slots[0].name == "delivery_time"


def test_conversation_defaults_metadata() -> None:
    conversation = Conversation(
        conversation_id="conv_1",
        instruction_id="instr_demo",
        turns=[Turn(turn_id=1, speaker="agent", text="您好，请问是王女士吗？")],
    )

    assert conversation.turns[0].speaker == "agent"
    assert conversation.metadata == {}
