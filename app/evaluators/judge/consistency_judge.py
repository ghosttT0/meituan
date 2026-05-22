from app.domain.conversation import Conversation
from app.domain.eval_spec import EvalSpec
from app.domain.evaluation_result import JudgeResult
from app.evaluators.judge.rubric_judge import RubricJudge


class ConsistencyJudge:
    def __init__(self, judge: RubricJudge, runs: int = 2) -> None:
        self.judge = judge
        self.runs = runs

    def evaluate(self, spec: EvalSpec, conversation: Conversation) -> list[list[JudgeResult]]:
        return [self.judge.evaluate(spec, conversation) for _ in range(self.runs)]
