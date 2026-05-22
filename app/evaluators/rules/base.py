from abc import ABC, abstractmethod

from app.domain.conversation import FactEvent
from app.domain.eval_spec import EvalSpec
from app.domain.evaluation_result import RuleResult


class Rule(ABC):
    @abstractmethod
    def evaluate(self, spec: EvalSpec, events: list[FactEvent]) -> RuleResult:
        raise NotImplementedError
