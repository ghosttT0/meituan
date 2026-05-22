from app.domain.task_instruction import TaskInstruction
from app.spec.mapper import InstructionIRMapper
from app.spec.normalizer import RuleFirstInstructionNormalizer
from app.spec.section_parser import InstructionSectionParser


class SpecCompiler:
    def __init__(
        self,
        parser: InstructionSectionParser | None = None,
        normalizer: RuleFirstInstructionNormalizer | None = None,
        mapper: InstructionIRMapper | None = None,
    ) -> None:
        self.parser = parser or InstructionSectionParser()
        self.normalizer = normalizer or RuleFirstInstructionNormalizer()
        self.mapper = mapper or InstructionIRMapper()

    def compile(self, instruction: TaskInstruction):
        ir = self.parser.parse(
            instruction_id=instruction.instruction_id,
            title=instruction.name,
            raw_text=instruction.raw_text,
        )
        if not ir.sections:
            return self._compile_legacy_keyword_spec(instruction)
        normalized = self.normalizer.normalize(ir)
        return self.mapper.to_eval_spec(normalized)

    def _compile_legacy_keyword_spec(self, instruction: TaskInstruction):
        ir = self.parser.parse_legacy_keywords(
            instruction_id=instruction.instruction_id,
            title=instruction.name,
            raw_text=instruction.raw_text,
        )
        normalized = self.normalizer.normalize(ir)
        return self.mapper.to_eval_spec(normalized)
