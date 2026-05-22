from app.domain.conversation import FactEvent
from app.domain.eval_spec import EvalSpec, ForbiddenAction, RequiredSlot, RequiredStep
from app.evaluators.rules.flow_rules import RequiredStepRule
from app.evaluators.rules.forbidden_rules import ForbiddenActionRule
from app.evaluators.rules.slot_rules import RequiredSlotRule
from app.pipeline.aggregator import Aggregator


def build_spec() -> EvalSpec:
    return EvalSpec(
        spec_id="spec_rule",
        instruction_id="instr_rule",
        version="v1",
        task_goal="确认收货时间",
        required_steps=[
            RequiredStep(
                id="identity_check",
                name="确认身份",
                order=1,
                required=True,
                evidence_requirement="身份确认",
            )
        ],
        required_slots=[
            RequiredSlot(name="delivery_time", required=True, accepted_values=["今天", "明天"])
        ],
        forbidden_actions=[
            ForbiddenAction(id="forbid_false_promise", description="禁止承诺一定送达")
        ],
    )


def test_required_slot_rule_passes_when_slot_filled() -> None:
    result = RequiredSlotRule().evaluate(
        build_spec(),
        [
            FactEvent(
                event_id="evt_1",
                event_type="slot_fill",
                turn_id=3,
                slot_name="delivery_time",
                slot_value="明天下午",
            )
        ],
    )

    assert result.passed is True
    assert result.reason == "已收集全部必填信息"


def test_forbidden_rule_fails_on_promise() -> None:
    result = ForbiddenActionRule().evaluate(
        build_spec(),
        [FactEvent(event_id="evt_2", event_type="promise", turn_id=4, note="一定送达")],
    )

    assert result.passed is False
    assert result.severity == "fatal"
    assert result.reason == "检测到禁止承诺"


def test_aggregator_zeroes_score_on_hard_fail() -> None:
    aggregate = Aggregator().combine(
        hard_results=[
            ForbiddenActionRule().evaluate(
                build_spec(), [FactEvent(event_id="evt_2", event_type="promise", turn_id=4)]
            )
        ],
        judge_results=[],
        parse_warnings=[],
    )

    assert aggregate["hard_fail"] is True
    assert aggregate["overall_score"] == 0.0
