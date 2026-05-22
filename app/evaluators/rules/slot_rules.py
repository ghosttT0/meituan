from app.domain.conversation import FactEvent
from app.domain.eval_spec import EvalSpec
from app.domain.evaluation_result import RuleResult
from app.evaluators.rules.base import Rule


class RequiredSlotRule(Rule):
    def evaluate(self, spec: EvalSpec, events: list[FactEvent]) -> RuleResult:
        filled_slots = {event.slot_name for event in events if event.event_type == "slot_fill"}
        required_slots = {slot.name for slot in spec.required_slots if slot.required}
        missing = sorted(required_slots - filled_slots)
        return RuleResult(
            rule_id="required_slots",
            passed=not missing,
            score_delta=1.0 if not missing else 0.0,
            evidence_turn_ids=[event.turn_id for event in events if event.event_type == "slot_fill"],
            reason="已收集全部必填信息" if not missing else f"缺少必填信息：{', '.join(missing)}",
        )
