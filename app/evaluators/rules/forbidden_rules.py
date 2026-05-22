from app.domain.conversation import FactEvent
from app.domain.eval_spec import EvalSpec
from app.domain.evaluation_result import RuleResult
from app.evaluators.rules.base import Rule


class ForbiddenActionRule(Rule):
    def evaluate(self, spec: EvalSpec, events: list[FactEvent]) -> RuleResult:
        forbidden_hit = [event for event in events if event.event_type == "promise"]
        return RuleResult(
            rule_id="forbidden_actions",
            passed=not forbidden_hit,
            score_delta=1.0 if not forbidden_hit else 0.0,
            severity="fatal" if forbidden_hit else "normal",
            evidence_turn_ids=[event.turn_id for event in forbidden_hit],
            reason="no forbidden action found" if not forbidden_hit else "forbidden promise detected",
        )
