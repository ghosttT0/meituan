from app.domain.conversation import Conversation
from app.domain.eval_spec import EvalSpec
from app.domain.evaluation_result import JudgeResult
from app.evaluators.judge.llm_adapter import LLMAdapter


class RubricJudge:
    def __init__(self, adapter: LLMAdapter) -> None:
        self.adapter = adapter

    def evaluate(self, spec: EvalSpec, conversation: Conversation) -> list[JudgeResult]:
        transcript = "\n".join(f"{turn.speaker}: {turn.text}" for turn in conversation.turns)
        results: list[JudgeResult] = []
        for dimension in spec.soft_dimensions:
            payload = self.adapter.score_dimension(dimension.id, dimension.rubric, transcript)
            results.append(JudgeResult(**payload))
        return results
