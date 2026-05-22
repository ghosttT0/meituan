from app.domain.simulation import ConversationState, ModelReplySignal, SimulationScenario, UserProfile


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
    ) -> str:
        history_text = "\n".join(f"{item['speaker']}: {item['text']}" for item in history) if history else "（当前无历史）"
        return f"""你正在扮演一个接电话的真实用户，而不是客服。

【用户画像】
- 画像名称：{profile.name}
- 风格约束：{profile.style_prompt or '根据画像自然表达'}

【场景约束】
- 当前任务目标：{task_goal}
- 当前主分支：{scenario.primary_branch}
- 当前状态：{state.current_state}
- 当前轮次：{state.turn_index}
- 建议意图：{suggested_action}

【模型上一轮表现信号】
- 是否解释原因：{signal.explained_reason}
- 是否触发违规承诺：{signal.triggered_forbidden_action}

【完整对话历史】
{history_text}

请你只站在用户角度回复。
输出严格使用 JSON：
{{
  "state": "<当前用户状态>",
  "intent": "<当前用户意图>",
  "reply": "<用户自然语言回复>",
  "should_end": <true/false>
}}
只返回 JSON，不要解释。"""
