import asyncio

from app.domain.eval_spec import EvalSpec, RequiredSlot, RequiredStep, SoftDimension
from app.domain.simulation import SimulatedUserReply
from app.simulators.conversation_runner import ConversationRunner


def build_spec() -> EvalSpec:
    return EvalSpec(
        spec_id="spec_sim",
        instruction_id="instr_sim",
        version="v2",
        task_goal="确认收货时间",
        role_definition="你是站长",
        opening_requirements=["您好，请问是张先生吗？"],
        flow_steps=[],
        faq_items=[],
        constraint_items=[],
        fallback_policy=[],
        required_steps=[
            RequiredStep(
                id="identity_check",
                name="确认身份",
                order=0,
                required=True,
                evidence_requirement="您好，请问是张先生吗？",
            )
        ],
        required_slots=[
            RequiredSlot(
                name="delivery_time",
                required=True,
                accepted_values=["今天", "明天", "下午"],
            )
        ],
        soft_dimensions=[
            SoftDimension(
                id="task_focus",
                name="任务聚焦度",
                weight=1.0,
                rubric=["保持任务推进"],
            )
        ],
    )


def test_conversation_runner_returns_turns_trace_and_evaluation() -> None:
    class _FakeUserLLM:
        def generate_turn(self, prompt: str):
            return SimulatedUserReply(
                state="cooperative",
                intent="answer_slot",
                reply="明天下午可以。",
                should_end=False,
            )

    runner = ConversationRunner(user_simulator=_FakeUserLLM())

    result = asyncio.run(
        runner.run_mock(
            spec=build_spec(),
            profile_id="cooperative",
            primary_branch="cooperative",
            max_turns=4,
        )
    )

    assert result.profile_id == "cooperative"
    assert result.turns
    assert result.state_trace[-1] == "terminated"
    assert "overall_score" in result.evaluation
    assert result.generation_mode == "ai"
    assert result.debug_logs


def test_conversation_runner_handles_busy_branch() -> None:
    class _FakeUserLLM:
        def generate_turn(self, prompt: str):
            return SimulatedUserReply(
                state="busy",
                intent="say_busy",
                reply="我现在有点忙，能快点说吗？",
                should_end=True,
            )

    runner = ConversationRunner(user_simulator=_FakeUserLLM())

    result = asyncio.run(
        runner.run_mock(
            spec=build_spec(),
            profile_id="busy",
            primary_branch="busy",
            max_turns=4,
        )
    )

    assert "busy" in result.state_trace
    assert result.termination_reason == "user_busy_end"


def test_conversation_runner_handles_questioning_branch() -> None:
    class _FakeUserLLM:
        def generate_turn(self, prompt: str):
            return SimulatedUserReply(
                state="questioning",
                intent="ask_why",
                reply="为什么必须这样？",
                should_end=False,
            )

    runner = ConversationRunner(user_simulator=_FakeUserLLM())

    result = asyncio.run(
        runner.run_mock(
            spec=build_spec(),
            profile_id="questioning",
            primary_branch="questioning",
            max_turns=4,
        )
    )

    assert "questioning" in result.state_trace
    assert result.scenario_key in {"custom", "faq_followup"}
    assert "overall_score" in result.evaluation
    assert any("问题池" in item for item in result.debug_logs)
    assert any("状态=" in item for item in result.debug_logs)
    assert any("被测模型 ->" in item for item in result.debug_logs)


def test_conversation_runner_falls_back_to_template_when_ai_user_fails() -> None:
    class _BrokenUserLLM:
        def generate_turn(self, prompt: str):
            return None

    runner = ConversationRunner(user_simulator=_BrokenUserLLM())

    result = asyncio.run(
        runner.run_mock(
            spec=build_spec(),
            profile_id="cooperative",
            primary_branch="cooperative",
            max_turns=2,
        )
    )

    assert result.generation_mode == "template_fallback"


def test_conversation_runner_uses_standard_scenario_metadata() -> None:
    class _FakeUserLLM:
        def generate_turn(self, prompt: str):
            return SimulatedUserReply(
                state="questioning",
                intent="ask_task_specific_question",
                reply="低延迟直播和标准直播差在哪？",
                should_end=False,
            )

    spec = EvalSpec(
        spec_id="spec_course",
        instruction_id="instr_course",
        version="v2",
        task_goal="告知机构客户低延迟直播和标准直播的区别。",
        flow_steps=[],
        faq_items=[],
        constraint_items=[],
        fallback_policy=[],
        required_steps=[],
        required_slots=[],
        soft_dimensions=[],
    )
    runner = ConversationRunner(user_simulator=_FakeUserLLM())

    result = asyncio.run(
        runner.run_mock(
            spec=spec,
            profile_id="cooperative",
            primary_branch="cooperative",
            max_turns=2,
            scenario_key="faq_followup",
        )
    )

    assert result.scenario_key == "faq_followup"
    assert "直播" in result.scenario_label
    assert "区别" in result.user_goal or "费用" in result.user_goal
    assert result.scenario_focus
    assert any("FAQ" in item or "知识点" in item for item in result.scenario_focus)
    assert result.scenario_diagnosis


def test_conversation_runner_builds_busy_scenario_focus() -> None:
    class _FakeUserLLM:
        def generate_turn(self, prompt: str):
            return SimulatedUserReply(
                state="busy",
                intent="say_busy",
                reply="我现在有点忙，你快说重点。",
                should_end=True,
            )

    spec = EvalSpec(
        spec_id="spec_rider",
        instruction_id="instr_rider",
        version="v2",
        task_goal='致电"飞毛腿"骑手，通知他们今天合同已成功签署，并提醒他们完成配送任务。',
        flow_steps=[],
        faq_items=[],
        constraint_items=[],
        fallback_policy=[],
        required_steps=[],
        required_slots=[],
        soft_dimensions=[],
    )
    runner = ConversationRunner(user_simulator=_FakeUserLLM())

    result = asyncio.run(
        runner.run_mock(
            spec=spec,
            profile_id="cooperative",
            primary_branch="cooperative",
            max_turns=2,
            scenario_key="busy_interrupt",
        )
    )

    assert result.scenario_key == "busy_interrupt"
    assert any("重点" in item or "忙碌" in item for item in result.scenario_focus)


def test_conversation_runner_builds_exit_scope_scenario_focus() -> None:
    class _FakeUserLLM:
        def generate_turn(self, prompt: str):
            return SimulatedUserReply(
                state="rejecting",
                intent="refuse",
                reply="这不是你们定的吗？你能不能直接改？",
                should_end=True,
            )

    spec = EvalSpec(
        spec_id="spec_rider",
        instruction_id="instr_rider",
        version="v2",
        task_goal='致电"飞毛腿"骑手，通知他们今天合同已成功签署，并提醒他们完成配送任务。',
        flow_steps=[],
        faq_items=[],
        constraint_items=[],
        fallback_policy=[],
        required_steps=[],
        required_slots=[],
        soft_dimensions=[],
    )
    runner = ConversationRunner(user_simulator=_FakeUserLLM())

    result = asyncio.run(
        runner.run_mock(
            spec=spec,
            profile_id="cooperative",
            primary_branch="cooperative",
            max_turns=2,
            scenario_key="exit_scope",
        )
    )

    assert result.scenario_key == "exit_scope"
    assert any("兜底" in item or "承诺" in item for item in result.scenario_focus)
