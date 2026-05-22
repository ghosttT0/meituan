from uuid import uuid4

from app.domain.eval_spec import (
    EvalSpec,
    ForbiddenAction,
    RequiredSlot,
    RequiredStep,
    SoftDimension,
)
from app.domain.task_instruction import TaskInstruction


class SpecCompiler:
    def compile(self, instruction: TaskInstruction) -> EvalSpec:
        required_steps: list[RequiredStep] = []
        required_slots: list[RequiredSlot] = []
        forbidden_actions: list[ForbiddenAction] = []

        if "身份" in instruction.raw_text:
            required_steps.append(
                RequiredStep(
                    id="identity_check",
                    name="确认身份",
                    order=1,
                    required=True,
                    evidence_requirement="需要明确身份确认话术",
                )
            )

        if "时间" in instruction.raw_text:
            required_slots.append(
                RequiredSlot(
                    name="delivery_time",
                    required=True,
                    accepted_values=["今天", "明天", "上午", "下午"],
                )
            )

        if "不要承诺" in instruction.raw_text or "不要保证" in instruction.raw_text:
            forbidden_actions.append(
                ForbiddenAction(
                    id="forbid_false_promise",
                    description="禁止承诺无法保证的送达结果",
                )
            )

        return EvalSpec(
            spec_id=f"spec_{uuid4().hex[:8]}",
            instruction_id=instruction.instruction_id,
            version="v1",
            task_goal=instruction.name,
            required_steps=required_steps,
            required_slots=required_slots,
            forbidden_actions=forbidden_actions,
            completion_conditions=["关键槽位完成或失败原因明确", "以结束语收尾"],
            hard_fail_conditions=["触发禁用承诺"],
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
