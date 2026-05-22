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
    assert "overall_score" in result.evaluation


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
