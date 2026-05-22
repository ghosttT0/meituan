from uuid import uuid4

from app.domain.eval_spec import (
    ConstraintItemSpec,
    EvalSpec,
    FAQItemSpec,
    FlowStepSpec,
    ForbiddenAction,
    RequiredSlot,
    RequiredStep,
    SoftDimension,
)
from app.spec.instruction_ir import InstructionIR


class InstructionIRMapper:
    def to_eval_spec(self, ir: InstructionIR) -> EvalSpec:
        required_steps = [
            RequiredStep(
                id=step.step_id,
                name=step.title,
                order=step.order,
                required=True,
                evidence_requirement=step.raw_text,
            )
            for step in ir.flow_steps
        ]
        if ir.opening_line and ("请问是" in ir.opening_line or "负责人吗" in ir.opening_line):
            required_steps.append(
                RequiredStep(
                    id="identity_check",
                    name="确认身份",
                    order=0,
                    required=True,
                    evidence_requirement=ir.opening_line,
                )
            )

        required_slots = []
        combined_text = "\n".join([ir.task_goal, ir.opening_line, *(step.raw_text for step in ir.flow_steps)])
        if "时间" in combined_text:
            required_slots.append(
                RequiredSlot(
                    name="delivery_time",
                    required=True,
                    accepted_values=["今天", "明天", "上午", "下午"],
                )
            )

        forbidden_actions = []
        if any(item.category == "forbidden_commitment" for item in ir.constraint_items):
            forbidden_actions.append(
                ForbiddenAction(
                    id="forbid_commitment",
                    description="禁止做出超出约束范围的承诺",
                )
            )

        return EvalSpec(
            spec_id=f"spec_{uuid4().hex[:8]}",
            instruction_id=ir.instruction_id,
            version="v2",
            task_goal=ir.task_goal or ir.title,
            role_definition=ir.role_definition,
            opening_requirements=[ir.opening_line] if ir.opening_line else [],
            flow_steps=[FlowStepSpec(**step.model_dump()) for step in ir.flow_steps],
            faq_items=[FAQItemSpec(**item.model_dump()) for item in ir.faq_items],
            constraint_items=[ConstraintItemSpec(**item.model_dump()) for item in ir.constraint_items],
            fallback_policy=ir.fallback_policy,
            required_steps=required_steps,
            required_slots=required_slots,
            forbidden_actions=forbidden_actions,
            completion_conditions=["完成关键流程步骤", "符合结束要求"],
            hard_fail_conditions=["触发禁止承诺"],
            soft_dimensions=[
                SoftDimension(
                    id="explanation_quality",
                    name="解释充分性",
                    weight=0.5,
                    rubric=["说明来电目的", "解释追问原因"],
                ),
                SoftDimension(
                    id="task_focus",
                    name="任务聚焦度",
                    weight=0.5,
                    rubric=["不跑题", "保持任务推进"],
                ),
            ],
            review_status="draft",
        )
