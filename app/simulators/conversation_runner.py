from uuid import uuid4

from app.domain.conversation import Conversation, Turn
from app.domain.eval_spec import EvalSpec
from app.domain.simulation import ConversationState, SimulatedUserReply, SimulationRunResult
from app.pipeline.evaluation_runner import EvaluationRunner
from app.simulators.ai_user_simulator import OpenAIUserSimulatorAdapter
from app.simulators.emotion_engine import EmotionEngine
from app.simulators.model_adapter import HttpModelAdapter, MockModelAdapter
from app.simulators.policy_engine import UserPolicyEngine
from app.simulators.profiles import get_profile
from app.simulators.prompt_builder import UserPromptBuilder
from app.simulators.question_pool import TaskQuestionPoolBuilder
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
        self.question_pool_builder = TaskQuestionPoolBuilder()
        self.user_simulator = user_simulator or OpenAIUserSimulatorAdapter()

    async def run_mock(
        self,
        spec: EvalSpec,
        profile_id: str,
        primary_branch: str,
        max_turns: int = 8,
        task_instruction_text: str = "",
        scenario_key: str | None = None,
        batch_runs: int = 1,
        random_seed: int | None = None,
        evaluation_mode: str = "dual_arbitration",
    ) -> SimulationRunResult:
        adapter = MockModelAdapter()
        return await self._run_batch(
            adapter,
            spec,
            profile_id,
            primary_branch,
            max_turns,
            task_instruction_text,
            scenario_key=scenario_key,
            batch_runs=batch_runs,
            random_seed=random_seed,
            evaluation_mode=evaluation_mode,
        )

    async def run_http(
        self,
        spec: EvalSpec,
        profile_id: str,
        primary_branch: str,
        endpoint: str,
        api_key: str = "",
        model: str = "",
        auth_type: str = "bearer",
        protocol_mode: str = "auto",
        max_turns: int = 8,
        task_instruction_text: str = "",
        scenario_key: str | None = None,
        batch_runs: int = 1,
        random_seed: int | None = None,
        evaluation_mode: str = "dual_arbitration",
    ) -> SimulationRunResult:
        adapter = HttpModelAdapter(endpoint=endpoint)
        return await self._run_batch(
            adapter,
            spec,
            profile_id,
            primary_branch,
            max_turns,
            task_instruction_text,
            {
                "api_key": api_key,
                "model": model,
                "auth_type": auth_type,
                "protocol_mode": protocol_mode,
            },
            scenario_key=scenario_key,
            batch_runs=batch_runs,
            random_seed=random_seed,
            evaluation_mode=evaluation_mode,
        )

    async def _run_batch(
        self,
        adapter,
        spec: EvalSpec,
        profile_id: str,
        primary_branch: str,
        max_turns: int,
        task_instruction_text: str,
        adapter_config: dict | None = None,
        scenario_key: str | None = None,
        batch_runs: int = 1,
        random_seed: int | None = None,
        evaluation_mode: str = "dual_arbitration",
    ) -> SimulationRunResult:
        if batch_runs <= 1:
            return await self._run(
                adapter,
                spec,
                profile_id,
                primary_branch,
                max_turns,
                task_instruction_text,
                adapter_config=adapter_config,
                scenario_key=scenario_key,
                random_seed=random_seed,
                evaluation_mode=evaluation_mode,
            )

        runs: list[SimulationRunResult] = []
        profile_distribution: dict[str, int] = {}
        for index in range(batch_runs):
            run_seed = (random_seed + index) if random_seed is not None else None
            run_result = await self._run(
                adapter,
                spec,
                profile_id,
                primary_branch,
                max_turns,
                task_instruction_text,
                adapter_config=adapter_config,
                scenario_key=scenario_key,
                random_seed=run_seed,
                evaluation_mode=evaluation_mode,
            )
            runs.append(run_result)
            profile_distribution[run_result.profile_id] = profile_distribution.get(run_result.profile_id, 0) + 1

        anchor = runs[0]
        avg_score = round(sum(item.evaluation.get("overall_score", 0) for item in runs) / max(len(runs), 1), 2)
        anchor.evaluation["overall_score"] = avg_score
        anchor.batch_mode = True
        anchor.batch_count = batch_runs
        anchor.profile_distribution = profile_distribution
        anchor.requested_profile_id = profile_id
        anchor.random_seed = random_seed
        anchor.runs = [
            {
                "simulation_id": item.simulation_id,
                "profile_id": item.profile_id,
                "overall_score": item.evaluation.get("overall_score", 0),
                "termination_reason": item.termination_reason,
            }
            for item in runs
        ]
        anchor.scenario_summary = f"{anchor.scenario_label}：已完成 {batch_runs} 次批量运行，平均分 {avg_score}"
        anchor.debug_logs = [
            *anchor.debug_logs,
            f"批量运行：共 {batch_runs} 次",
            f"画像分布：{profile_distribution}",
            f"平均得分：{avg_score}",
        ]
        return anchor

    async def _run(
        self,
        adapter,
        spec: EvalSpec,
        profile_id: str,
        primary_branch: str,
        max_turns: int,
        task_instruction_text: str,
        adapter_config: dict | None = None,
        scenario_key: str | None = None,
        random_seed: int | None = None,
        evaluation_mode: str = "dual_arbitration",
    ) -> SimulationRunResult:
        scenario = self.scenario_builder.build(
            spec,
            profile_id=profile_id,
            primary_branch=primary_branch,
            max_turns=max_turns,
            scenario_key=scenario_key,
            random_seed=random_seed,
        )
        profile = get_profile(scenario.profile_id)
        question_pool = self.question_pool_builder.build(spec)
        state = ConversationState(current_state="init", turn_index=0)
        state_trace = [state.current_state]
        turns: list[dict] = []
        signal = self.reply_analyzer.analyze("")
        generation_mode = "ai"
        recent_questions: list[str] = []
        debug_logs: list[str] = []
        emotion_engine = EmotionEngine(profile)

        session_config = {
            "task_instruction_text": task_instruction_text or spec.task_goal,
            **(adapter_config or {}),
        }
        debug_logs.append(
            f"启动模拟：场景={scenario.scenario_label or scenario.scenario_key}，画像={profile.name}，主分支={scenario.primary_branch}，适配器={'真实模型接口' if adapter_config else 'Mock演示'}"
        )
        debug_logs.append(f"用户目标：{scenario.user_goal}")
        debug_logs.append(f"任务目标：{spec.task_goal}")
        await adapter.start_session(session_config)

        for turn_index in range(max_turns):
            suggested_intent = self.policy_engine.next_intent(
                primary_branch=scenario.primary_branch,
                state=state,
                signal=signal,
                question_pool=question_pool,
                recent_questions=recent_questions,
                profile=profile,
            )
            if suggested_intent.note:
                debug_logs.append(
                    f"第{turn_index + 1}轮：状态={state.current_state}，意图={suggested_intent.action}，从任务问题池选择 -> {suggested_intent.note}"
                )
            else:
                debug_logs.append(
                    f"第{turn_index + 1}轮：状态={state.current_state}，意图={suggested_intent.action}，未命中任务问题池"
                )
            prompt = self.prompt_builder.build(
                profile=profile,
                scenario=scenario,
                state=state,
                task_goal=spec.task_goal,
                history=turns,
                suggested_action=suggested_intent.action,
                signal=signal,
                question_pool=question_pool,
                emotion=emotion_engine.emotion,
            )
            if suggested_intent.note:
                recent_questions.append(suggested_intent.note)
            ai_reply = self.user_simulator.generate_turn(prompt)

            if ai_reply is None:
                generation_mode = "template_fallback"
                debug_logs.append(f"第{turn_index + 1}轮：AI 用户模拟失败，切换模板兜底")
                ai_reply = SimulatedUserReply(
                    state=suggested_intent.state,
                    intent=suggested_intent.action,
                    reply=self.response_generator.render(suggested_intent, profile, emotion=emotion_engine.emotion),
                    should_end=suggested_intent.state in {"busy", "rejecting"},
                )

            user_text = ai_reply.reply
            model_reply = await adapter.send_user_message(user_text)
            debug_logs.append(f"第{turn_index + 1}轮：模拟用户 -> {user_text}")
            debug_logs.append(f"第{turn_index + 1}轮：被测模型 -> {model_reply}")
            turns.append({"turn_id": len(turns) + 1, "speaker": "user", "text": user_text})
            turns.append({"turn_id": len(turns) + 1, "speaker": "agent", "text": model_reply})

            signal = self.reply_analyzer.analyze(model_reply)
            current_emotion = emotion_engine.step(signal, turn_index)
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
            debug_logs.append(
                f"第{turn_index + 1}轮：模型信号 explained_reason={signal.explained_reason} triggered_forbidden={signal.triggered_forbidden_action} 用户情绪={current_emotion}"
            )

            if ai_reply.should_end or ai_reply.state in {"busy", "rejecting"}:
                if state_trace[-1] != "terminated":
                    state_trace.append("terminated")
                debug_logs.append(f"第{turn_index + 1}轮：用户选择结束，终止模拟")
                break

        await adapter.end_session()

        conversation = Conversation(
            conversation_id=f"simulation_{uuid4().hex[:8]}",
            instruction_id=spec.instruction_id,
            source="simulation",
            turns=[Turn(**turn) for turn in turns],
            metadata={
                "scenario_key": scenario.scenario_key,
                "scenario_label": scenario.scenario_label,
                "user_goal": scenario.user_goal,
            },
        )
        evaluation = EvaluationRunner().run(
            spec,
            conversation,
            evaluation_mode=evaluation_mode,
        ).model_dump()
        scenario_focus = self._build_scenario_focus(scenario.scenario_key)
        scenario_diagnosis = self._build_scenario_diagnosis(scenario.scenario_key, evaluation, state_trace, debug_logs)
        scenario_summary = self._build_scenario_summary(
            scenario.scenario_key,
            scenario.scenario_label,
            evaluation,
        )

        return SimulationRunResult(
            simulation_id=f"sim_{uuid4().hex[:8]}",
            scenario_id=scenario.scenario_id,
            scenario_key=scenario.scenario_key,
            scenario_label=scenario.scenario_label,
            user_goal=scenario.user_goal,
            scenario_focus=scenario_focus,
            scenario_diagnosis=scenario_diagnosis,
            scenario_summary=scenario_summary,
            batch_mode=False,
            batch_count=1,
            profile_distribution={scenario.profile_id: 1},
            requested_profile_id=profile_id,
            random_seed=random_seed,
            profile_id=scenario.profile_id,
            termination_reason="user_busy_end" if "busy" in state_trace else "task_complete",
            generation_mode=generation_mode,
            adapter_mode="http" if isinstance(adapter, HttpModelAdapter) else "mock",
            state_trace=state_trace if state_trace[-1] == "terminated" else [*state_trace, "terminated"],
            turns=turns,
            evaluation=evaluation,
            debug_logs=debug_logs,
        )

    def _build_scenario_focus(self, scenario_key: str) -> list[str]:
        mapping = {
            "main_flow": ["重点检查主流程步骤是否完整执行", "重点检查任务目标是否真正完成"],
            "faq_followup": ["重点检查 FAQ / 知识点是否答到位", "重点检查模型是否保持任务聚焦"],
            "busy_interrupt": ["重点检查是否快速说重点", "重点检查是否尊重用户忙碌状态"],
            "hesitant_risk": ["重点检查是否解释风险/影响/费用", "重点检查是否能消除用户犹豫"],
            "exit_scope": ["重点检查是否正确兜底", "重点检查是否触发违规承诺"],
        }
        return mapping.get(scenario_key, ["重点检查任务目标完成情况", "重点检查关键流程和限制项"])

    def _build_scenario_diagnosis(
        self,
        scenario_key: str,
        evaluation: dict,
        state_trace: list[str],
        debug_logs: list[str],
    ) -> list[str]:
        diagnosis: list[str] = []
        hard_fail = evaluation.get("hard_fail", False)
        score = evaluation.get("overall_score", 0)
        if scenario_key == "faq_followup":
            diagnosis.append("本场景主要看模型是否回答了用户追问的关键知识点。")
            if score < 70:
                diagnosis.append("FAQ 追问场景得分偏低，说明知识点解释或追问处理可能不足。")
        elif scenario_key == "busy_interrupt":
            diagnosis.append("本场景主要看模型能否快速聚焦并尊重忙碌/打断信号。")
            if "busy" in state_trace:
                diagnosis.append("用户在忙碌状态下结束，建议检查模型是否过于冗长。")
        elif scenario_key == "hesitant_risk":
            diagnosis.append("本场景主要看模型是否解释清楚风险、影响或费用。")
            if score < 70:
                diagnosis.append("犹豫场景得分偏低，说明风险解释或安抚不足。")
        elif scenario_key == "exit_scope":
            diagnosis.append("本场景主要看模型是否正确兜底、避免超纲承诺。")
            if hard_fail:
                diagnosis.append("退出/超纲场景命中了硬性失败项，优先排查违规承诺或收尾不当。")
        else:
            diagnosis.append("本场景主要看主流程推进和任务完成度。")

        if not diagnosis:
            diagnosis.append("当前场景暂无额外诊断。")
        return diagnosis

    def _build_scenario_summary(
        self,
        scenario_key: str,
        scenario_label: str,
        evaluation: dict,
    ) -> str:
        scenario_rules = [item for item in evaluation.get("rule_results", []) if str(item.get("rule_id", "")).startswith("scenario_")]
        failed_rules = [item for item in scenario_rules if not item.get("passed", False)]
        if failed_rules:
            return f"{scenario_label or scenario_key}：{failed_rules[0].get('reason', '存在场景性失败')}"
        if scenario_rules:
            return f"{scenario_label or scenario_key}：场景附加规则通过"
        return f"{scenario_label or scenario_key}：按主流程完成评测"
