from app.domain.conversation import FactEvent
from app.domain.eval_spec import EvalSpec
from app.domain.evaluation_result import RuleResult
from app.evaluators.rules.base import Rule


class RequiredStepRule(Rule):
    def evaluate(self, spec: EvalSpec, events: list[FactEvent]) -> RuleResult:
        required_ids = {step.id for step in spec.required_steps if step.required}
        observed = {event.event_type for event in events}
        missing = sorted(required_ids - observed)
        return RuleResult(
            rule_id="required_steps",
            passed=not missing,
            score_delta=1.0 if not missing else 0.0,
            evidence_turn_ids=[event.turn_id for event in events if event.event_type in required_ids],
            reason="已完成全部必做步骤" if not missing else f"缺少必做步骤：{', '.join(missing)}",
        )
