from app.domain.conversation import Conversation, FactEvent, Turn
from app.domain.eval_spec import ConstraintItemSpec, EvalSpec, FAQItemSpec
from app.evaluators.rules.scenario_rules import ScenarioRuleEngine


def test_scenario_rule_engine_passes_faq_grounding_rule() -> None:
    spec = EvalSpec(
        spec_id="spec_course",
        instruction_id="instr_course",
        version="v2",
        task_goal="告知机构客户低延迟直播和标准直播的区别。",
        faq_items=[
            FAQItemSpec(faq_id="faq_1", raw_text="低延迟直播更适合小班课，费用略高。"),
            FAQItemSpec(faq_id="faq_2", raw_text="标准直播更适合大班课。"),
        ],
    )
    conversation = Conversation(
        conversation_id="conv_1",
        instruction_id="instr_course",
        turns=[
            Turn(turn_id=1, speaker="user", text="低延迟直播和标准直播差在哪？"),
            Turn(turn_id=2, speaker="agent", text="低延迟直播更适合小班课，标准直播适合大班课，费用也不同。"),
        ],
        metadata={"scenario_key": "faq_followup"},
    )

    results = ScenarioRuleEngine().evaluate(spec, conversation, [])

    rule = next(item for item in results if item.rule_id == "scenario_faq_grounding")
    assert rule.passed is True
    assert "知识点" in rule.reason or "FAQ" in rule.reason


def test_scenario_rule_engine_fails_busy_focus_rule_when_agent_is_verbose() -> None:
    spec = EvalSpec(
        spec_id="spec_busy",
        instruction_id="instr_busy",
        version="v2",
        task_goal="确认直播升级通知",
    )
    conversation = Conversation(
        conversation_id="conv_2",
        instruction_id="instr_busy",
        turns=[
            Turn(turn_id=1, speaker="user", text="我现在有点忙，你快说重点。"),
            Turn(
                turn_id=2,
                speaker="agent",
                text="这边想和您详细说明我们本次产品升级的全部背景、原因、差异、费用和后续配置步骤，可能需要几分钟时间。",
            ),
        ],
        metadata={"scenario_key": "busy_interrupt"},
    )

    results = ScenarioRuleEngine().evaluate(spec, conversation, [])

    rule = next(item for item in results if item.rule_id == "scenario_busy_focus")
    assert rule.passed is False
    assert "重点" in rule.reason or "冗长" in rule.reason


def test_scenario_rule_engine_passes_exit_scope_rule_with_fallback() -> None:
    spec = EvalSpec(
        spec_id="spec_rider",
        instruction_id="instr_rider",
        version="v2",
        task_goal='致电"飞毛腿"骑手，通知他们今天合同已成功签署，并提醒他们完成配送任务。',
        constraint_items=[
            ConstraintItemSpec(
                constraint_id="c_1",
                raw_text='如被问及超出职责范围的问题，回复："我向同事确认后再回电给你。我现在能回答的先回答。"',
            )
        ],
        fallback_policy=["我向同事确认后再回电给你。我现在能回答的先回答。"],
    )
    conversation = Conversation(
        conversation_id="conv_3",
        instruction_id="instr_rider",
        turns=[
            Turn(turn_id=1, speaker="user", text="这不是你们定的吗？你能不能直接改？"),
            Turn(turn_id=2, speaker="agent", text="这个我先向同事确认后再回电给你，我现在能回答的先回答。"),
        ],
        metadata={"scenario_key": "exit_scope"},
    )

    results = ScenarioRuleEngine().evaluate(spec, conversation, [FactEvent(event_id="evt_1", event_type="other", turn_id=1)])

    rule = next(item for item in results if item.rule_id == "scenario_scope_fallback")
    assert rule.passed is True
    assert "兜底" in rule.reason or "回电" in rule.reason


def test_scenario_rule_engine_passes_hesitant_risk_rule_with_impact_explanation() -> None:
    spec = EvalSpec(
        spec_id="spec_hesitant",
        instruction_id="instr_hesitant",
        version="v2",
        task_goal="告知机构客户低延迟直播和标准直播的区别。",
    )
    conversation = Conversation(
        conversation_id="conv_4",
        instruction_id="instr_hesitant",
        turns=[
            Turn(turn_id=1, speaker="user", text="费用会不会更高？不这么做会有什么影响？"),
            Turn(turn_id=2, speaker="agent", text="低延迟直播费用会略高一些，但互动更顺，不同课程可以按需选择。"),
        ],
        metadata={"scenario_key": "hesitant_risk"},
    )

    results = ScenarioRuleEngine().evaluate(spec, conversation, [])

    rule = next(item for item in results if item.rule_id == "scenario_hesitant_clarity")
    assert rule.passed is True
    assert "风险" in rule.reason or "费用" in rule.reason or "影响" in rule.reason
