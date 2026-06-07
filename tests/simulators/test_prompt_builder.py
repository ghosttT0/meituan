from app.domain.simulation import ConversationState, ModelReplySignal, SimulationScenario, UserProfile
from app.domain.eval_spec import EvalSpec, FAQItemSpec, FlowStepSpec
from app.simulators.question_pool import TaskQuestionPoolBuilder
from app.simulators.prompt_builder import UserPromptBuilder


def test_prompt_builder_includes_profile_scenario_and_history() -> None:
    builder = UserPromptBuilder()
    profile = UserProfile(
        profile_id="busy",
        name="忙碌型",
        cooperation_level=0.4,
        patience_level=0.2,
        style_prompt="说话简短，优先表达自己很忙。",
    )
    scenario = SimulationScenario(
        scenario_id="scenario_1",
        spec_id="spec_1",
        profile_id="busy",
        primary_branch="busy",
        scenario_key="busy_interrupt",
        scenario_label="忙碌打断",
        user_goal="在忙碌情况下要求对方快速说明重点",
        max_turns=6,
        termination_policy="task_complete_or_user_exit",
    )
    state = ConversationState(current_state="busy", turn_index=2)
    signal = ModelReplySignal(answered_question=False, explained_reason=False)

    prompt = builder.build(
        profile=profile,
        scenario=scenario,
        state=state,
        task_goal="确认收货时间",
        history=[
            {"speaker": "agent", "text": "您好，请问您明天下午方便收货吗？"},
            {"speaker": "user", "text": "我现在有点忙。"},
        ],
        suggested_action="say_busy",
        signal=signal,
    )

    assert "忙碌型" in prompt
    assert "确认收货时间" in prompt
    assert "当前状态：busy" in prompt
    assert "当前测试场景：忙碌打断" in prompt
    assert "当前用户目标：在忙碌情况下要求对方快速说明重点" in prompt
    assert "建议意图：say_busy" in prompt
    assert "agent: 您好，请问您明天下午方便收货吗？" in prompt
    assert "你不能扮演客服" in prompt
    assert "如果模型已经解释清楚" in prompt


def test_prompt_builder_includes_task_specific_candidate_questions() -> None:
    builder = UserPromptBuilder()
    spec = EvalSpec(
        spec_id="spec_course",
        instruction_id="instr_course",
        version="v2",
        task_goal="告知机构客户低延迟直播和标准直播的区别。",
        flow_steps=[
            FlowStepSpec(
                step_id="step_1",
                order=1,
                title="传达升级内容",
                raw_text="说明标准直播与低延迟直播的区别。",
            )
        ],
        faq_items=[
            FAQItemSpec(faq_id="faq_1", raw_text="低延迟直播更适合小班课，费用略高。"),
        ],
    )
    pool = TaskQuestionPoolBuilder().build(spec)
    profile = UserProfile(
        profile_id="questioning",
        name="追问型",
        cooperation_level=0.6,
        patience_level=0.7,
        style_prompt="会追问区别、费用和规则原因。",
    )
    scenario = SimulationScenario(
        scenario_id="scenario_1",
        spec_id="spec_course",
        profile_id="questioning",
        primary_branch="questioning",
        scenario_key="faq_followup",
        scenario_label="直播 FAQ 追问",
        user_goal="追问低延迟直播和标准直播的区别及费用变化",
        max_turns=6,
        termination_policy="task_complete_or_user_exit",
    )
    state = ConversationState(current_state="questioning", turn_index=1)
    signal = ModelReplySignal(answered_question=False, explained_reason=False)

    prompt = builder.build(
        profile=profile,
        scenario=scenario,
        state=state,
        task_goal=spec.task_goal,
        history=[{"speaker": "agent", "text": "我们新增了低延迟直播。"}],
        suggested_action="ask_why",
        signal=signal,
        question_pool=pool,
    )

    assert "任务相关可选问题" in prompt
    assert "当前测试场景：直播 FAQ 追问" in prompt
    assert "低延迟直播和标准直播差在哪" in prompt or "费用会不会更高" in prompt
