from uuid import uuid4

from app.domain.conversation import Conversation, Turn
from app.domain.eval_spec import EvalSpec
from app.domain.simulation import ConversationState, SimulatedUserReply, SimulationRunResult
from app.pipeline.evaluation_runner import EvaluationRunner
from app.simulators.ai_user_simulator import OpenAIUserSimulatorAdapter
from app.simulators.model_adapter import HttpModelAdapter, MockModelAdapter
from app.simulators.policy_engine import UserPolicyEngine
from app.simulators.profiles import get_profile
from app.simulators.prompt_builder import UserPromptBuilder
from app.simulators.reply_analyzer import RuleBasedReplyAnalyzer
from app.simulators.response_generator import TemplateFirstResponseGenerator
from app.simulators.scenario_builder import ScenarioBuilder


class ConversationRunner:
    def __init__(self, user_simulator: OpenAIUserSimulatorAdapter | None = None) -> None:
        self.scenario_builder = ScenarioBuilder()
        self.policy_engine = UserPolicyEngine()
        self.response_generator = TemplateFirstResponseGenerator()
        self.reply_analyzer = RuleBasedReplyAnalyzer()
        self.prompt_builder = UserPromptBuilder()
        self.user_simulator = user_simulator or OpenAIUserSimulatorAdapter()

    async def run_mock(
        self,
        spec: EvalSpec,
        profile_id: str,
        primary_branch: str,
        max_turns: int = 8,
        task_instruction_text: str = "",
    ) -> SimulationRunResult:
        adapter = MockModelAdapter()
        return await self._run(
            adapter, spec, profile_id, primary_branch, max_turns, task_instruction_text
        )

    async def run_http(
        self,
        spec: EvalSpec,
        profile_id: str,
        primary_branch: str,
        endpoint: str,
        max_turns: int = 8,
        task_instruction_text: str = "",
    ) -> SimulationRunResult:
        adapter = HttpModelAdapter(endpoint=endpoint)
        return await self._run(
            adapter, spec, profile_id, primary_branch, max_turns, task_instruction_text
        )

    async def _run(
        self,
        adapter,
        spec: EvalSpec,
        profile_id: str,
        primary_branch: str,
        max_turns: int,
        task_instruction_text: str,
    ) -> SimulationRunResult:
        scenario = self.scenario_builder.build(
            spec, profile_id=profile_id, primary_branch=primary_branch, max_turns=max_turns
        )
        profile = get_profile(profile_id)
        state = ConversationState(current_state="init", turn_index=0)
        state_trace = [state.current_state]
        turns: list[dict] = []
        signal = self.reply_analyzer.analyze("")
        generation_mode = "ai"

        await adapter.start_session({"task_instruction_text": task_instruction_text or spec.task_goal})

        for turn_index in range(max_turns):
            suggested_intent = self.policy_engine.next_intent(
                primary_branch=primary_branch, state=state, signal=signal
            )
            prompt = self.prompt_builder.build(
                profile=profile,
                scenario=scenario,
                state=state,
                task_goal=spec.task_goal,
                history=turns,
                suggested_action=suggested_intent.action,
                signal=signal,
            )
            ai_reply = self.user_simulator.generate_turn(prompt)

            if ai_reply is None:
                generation_mode = "template_fallback"
                ai_reply = SimulatedUserReply(
                    state=suggested_intent.state,
                    intent=suggested_intent.action,
                    reply=self.response_generator.render(suggested_intent, profile),
                    should_end=suggested_intent.state in {"busy", "rejecting"},
                )

            user_text = ai_reply.reply
            model_reply = await adapter.send_user_message(user_text)
            turns.append({"turn_id": len(turns) + 1, "speaker": "user", "text": user_text})
            turns.append({"turn_id": len(turns) + 1, "speaker": "agent", "text": model_reply})

            signal = self.reply_analyzer.analyze(model_reply)
            next_state = (
                "terminated"
                if turn_index == max_turns - 1 and not ai_reply.should_end
                else ai_reply.state
            )
            state = ConversationState(
                current_state=next_state,
                turn_index=turn_index + 1,
            )
            state_trace.append(state.current_state)

            if ai_reply.should_end or ai_reply.state in {"busy", "rejecting"}:
                if state_trace[-1] != "terminated":
                    state_trace.append("terminated")
                break

        await adapter.end_session()

        conversation = Conversation(
            conversation_id=f"simulation_{uuid4().hex[:8]}",
            instruction_id=spec.instruction_id,
            source="simulation",
            turns=[Turn(**turn) for turn in turns],
        )
        evaluation = EvaluationRunner().run(spec, conversation).model_dump()

        return SimulationRunResult(
            simulation_id=f"sim_{uuid4().hex[:8]}",
            scenario_id=scenario.scenario_id,
            profile_id=profile_id,
            termination_reason="user_busy_end" if "busy" in state_trace else "task_complete",
            generation_mode=generation_mode,
            state_trace=state_trace if state_trace[-1] == "terminated" else [*state_trace, "terminated"],
            turns=turns,
            evaluation=evaluation,
        )
