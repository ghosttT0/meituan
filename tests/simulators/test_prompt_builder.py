from app.domain.simulation import ConversationState, ModelReplySignal, SimulationScenario, UserProfile
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
    assert "建议意图：say_busy" in prompt
    assert "agent: 您好，请问您明天下午方便收货吗？" in prompt
    assert "你不能扮演客服" in prompt
    assert "如果模型已经解释清楚" in prompt
