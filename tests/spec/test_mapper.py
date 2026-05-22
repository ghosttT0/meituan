from app.spec.instruction_ir import IRConstraintItem, IRFAQItem, IRFlowStep, InstructionIR
from app.spec.mapper import InstructionIRMapper


def test_mapper_builds_enhanced_eval_spec_fields() -> None:
    ir = InstructionIR(
        instruction_id="instr_demo",
        title="demo",
        role_definition="你是客服",
        task_goal="通知升级",
        opening_line="您好，请问您是负责人吗？",
        flow_steps=[IRFlowStep(step_id="step_1", order=1, title="身份确认", raw_text="确认负责人身份")],
        faq_items=[IRFAQItem(faq_id="faq_1", raw_text="低延迟直播适合强互动")],
        constraint_items=[IRConstraintItem(constraint_id="constraint_1", raw_text="每次回复15-20个字", category="length_limit")],
        fallback_policy=["若商家说在开车，礼貌说稍后再打。"],
    )

    spec = InstructionIRMapper().to_eval_spec(ir)

    assert spec.role_definition == "你是客服"
    assert spec.opening_requirements[0] == "您好，请问您是负责人吗？"
    assert spec.flow_steps[0].title == "身份确认"
    assert spec.constraint_items[0].category == "length_limit"
    assert spec.faq_items[0].raw_text == "低延迟直播适合强互动"
    assert spec.required_steps[0].id == "step_1"


def test_mapper_keeps_legacy_rule_fields_for_existing_evaluator() -> None:
    ir = InstructionIR(
        instruction_id="instr_legacy",
        title="demo",
        task_goal="确认收货时间",
        opening_line="您好，请问是张先生吗？",
        flow_steps=[IRFlowStep(step_id="step_1", order=1, title="身份确认", raw_text="确认负责人身份")],
        constraint_items=[
            IRConstraintItem(
                constraint_id="constraint_1",
                raw_text="不能承诺给商家优惠券",
                category="forbidden_commitment",
            )
        ],
    )

    spec = InstructionIRMapper().to_eval_spec(ir)

    assert any(item.id == "identity_check" for item in spec.required_steps)
    assert spec.required_slots[0].name == "delivery_time"
    assert spec.forbidden_actions[0].id == "forbid_commitment"
