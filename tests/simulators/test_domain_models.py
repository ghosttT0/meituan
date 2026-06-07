from app.domain.simulation import (
    ConversationState,
    ModelReplySignal,
    SimulatedUserReply,
    SimulationRunResult,
    SimulationScenario,
    UserIntent,
    UserProfile,
)


def test_simulation_scenario_defaults() -> None:
    scenario = SimulationScenario(
        scenario_id="scenario_1",
        spec_id="spec_1",
        profile_id="cooperative",
        primary_branch="cooperative",
        max_turns=8,
        termination_policy="task_complete_or_user_exit",
    )

    assert scenario.primary_branch == "cooperative"
    assert scenario.coverage_mode == "primary"


def test_user_intent_and_reply_signal_models() -> None:
    intent = UserIntent(action="ask_why", state="questioning", target_step_id="step_2")
    signal = ModelReplySignal(
        answered_question=True,
        explained_reason=True,
        followed_flow_step="step_2",
        triggered_forbidden_action=False,
        ignored_user_state=False,
    )

    assert intent.action == "ask_why"
    assert signal.followed_flow_step == "step_2"


def test_simulation_run_result_contains_trace_and_evaluation() -> None:
    result = SimulationRunResult(
        simulation_id="sim_1",
        scenario_id="scenario_1",
        profile_id="busy",
        termination_reason="user_busy_end",
        state_trace=["init", "busy", "terminated"],
        turns=[],
        evaluation={"overall_score": 72},
    )

    assert result.state_trace[-1] == "terminated"
    assert result.evaluation["overall_score"] == 72


def test_simulated_user_reply_model() -> None:
    reply = SimulatedUserReply(
        state="questioning",
        intent="ask_why",
        reply="为什么必须这样？",
        should_end=False,
    )

    assert reply.state == "questioning"
    assert reply.reply == "为什么必须这样？"


def test_user_profile_supports_question_pool_preferences() -> None:
    profile = UserProfile(
        profile_id="questioning",
        name="追问型",
        cooperation_level=0.6,
        patience_level=0.7,
        question_probability=0.9,
        preferred_question_sources=["faq", "step"],
        max_question_rounds=3,
    )

    assert profile.preferred_question_sources == ["faq", "step"]
    assert profile.max_question_rounds == 3
