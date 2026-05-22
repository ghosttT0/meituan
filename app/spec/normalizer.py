from typing import Protocol

from app.spec.instruction_ir import InstructionIR


class InstructionNormalizer(Protocol):
    def normalize(self, ir: InstructionIR) -> InstructionIR:
        ...


class RuleFirstInstructionNormalizer:
    def normalize(self, ir: InstructionIR) -> InstructionIR:
        updated_constraints = []
        fallback_policy: list[str] = list(ir.fallback_policy)

        for item in ir.constraint_items:
            category = self._classify(item.raw_text)
            updated_constraints.append(item.model_copy(update={"category": category}))

            if "超出职责范围" in item.raw_text or "稍后再打" in item.raw_text or "挂断" in item.raw_text:
                fallback_policy.append(item.raw_text)

        return ir.model_copy(
            update={
                "constraint_items": updated_constraints,
                "fallback_policy": fallback_policy,
            }
        )

    def _classify(self, text: str) -> str:
        if "字以内" in text or "15-20个字" in text:
            return "length_limit"
        if "不能承诺" in text or "不承诺" in text or "折扣券" in text or "优惠券" in text:
            return "forbidden_commitment"
        if "语气" in text or "口语化" in text:
            return "style_constraint"
        if "超出职责范围" in text or "稍后再打" in text or "挂断" in text:
            return "fallback_policy"
        return "general_constraint"
