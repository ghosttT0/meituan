from app.domain.simulation import ConversationState, ModelReplySignal, SimulationScenario, UserProfile
from app.simulators.emotion_engine import EMOTION_PROMPTS
from app.simulators.question_pool import TaskQuestionPool


class UserPromptBuilder:
    def build(
        self,
        profile: UserProfile,
        scenario: SimulationScenario,
        state: ConversationState,
        task_goal: str,
        history: list[dict],
        suggested_action: str,
        signal: ModelReplySignal,
        question_pool: TaskQuestionPool | None = None,
        emotion: str = "neutral",
    ) -> str:
        history_text = "\n".join(f"{item['speaker']}: {item['text']}" for item in history) if history else "（当前无历史）"
        question_text = "（当前无任务相关可选问题）"
        if question_pool:
            all_questions = [
                *[item.prompt_text for item in question_pool.faq_questions],
                *[item.prompt_text for item in question_pool.step_questions],
                *[item.prompt_text for item in question_pool.objection_questions],
            ]
            if all_questions:
                question_text = "\n".join(f"- {item}" for item in all_questions)
        emotion_hint = EMOTION_PROMPTS.get(emotion, EMOTION_PROMPTS["neutral"])
        return f"""你正在扮演一个接电话的真实用户。
你不能扮演客服，也不能替客服推进任务。

【用户画像】
- 画像名称：{profile.name}
- 风格约束：{profile.style_prompt or '根据画像自然表达'}
- 当前情绪：{emotion_hint}

【场景约束】
- 当前任务目标：{task_goal}
- 当前测试场景：{scenario.scenario_label or scenario.scenario_key}
- 当前用户目标：{scenario.user_goal or task_goal}
- 当前主分支：{scenario.primary_branch}
- 当前状态：{state.current_state}
- 当前轮次：{state.turn_index}
- 建议意图：{suggested_action}

【模型上一轮表现信号】
- 是否解释原因：{signal.explained_reason}
- 是否触发违规承诺：{signal.triggered_forbidden_action}

【完整对话历史】
{history_text}

【任务相关可选问题】
{question_text}

如果模型已经解释清楚，就不要机械重复同一句追问。
如果模型没有解释清楚，再按照建议意图继续追问或表达阻碍。
如果建议意图是任务相关追问，请优先围绕上面的任务相关可选问题来问，不要泛泛地重复“为什么必须这样”。
请你只站在用户角度回复。
输出严格使用 JSON：
{{
  "state": "<当前用户状态>",
  "intent": "<当前用户意图>",
  "reply": "<用户自然语言回复>",
  "should_end": <true/false>
}}
只返回 JSON，不要解释。"""
