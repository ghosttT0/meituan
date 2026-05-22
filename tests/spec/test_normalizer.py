from app.spec.instruction_ir import IRConstraintItem, InstructionIR
from app.spec.normalizer import RuleFirstInstructionNormalizer


def test_normalizer_classifies_constraint_categories() -> None:
    ir = InstructionIR(
        instruction_id="instr_1",
        title="demo",
        constraint_items=[
            IRConstraintItem(constraint_id="constraint_1", raw_text="每次回复控制在约30个字以内。"),
            IRConstraintItem(constraint_id="constraint_2", raw_text="不能承诺给商家折扣券或优惠券。"),
        ],
    )

    normalized = RuleFirstInstructionNormalizer().normalize(ir)

    assert normalized.constraint_items[0].category == "length_limit"
    assert normalized.constraint_items[1].category == "forbidden_commitment"


def test_normalizer_extracts_fallback_policy_from_constraints() -> None:
    ir = InstructionIR(
        instruction_id="instr_2",
        title="demo",
        constraint_items=[
            IRConstraintItem(
                constraint_id="constraint_1",
                raw_text='如被问及超出职责范围的问题，回复："我向同事确认后再回电给你。"',
            ),
            IRConstraintItem(
                constraint_id="constraint_2",
                raw_text="若商家说在开车，礼貌说“那我稍后再打”后挂断。",
            ),
        ],
    )

    normalized = RuleFirstInstructionNormalizer().normalize(ir)

    assert len(normalized.fallback_policy) == 2
    assert "超出职责范围" in normalized.fallback_policy[0]
    assert "开车" in normalized.fallback_policy[1]
