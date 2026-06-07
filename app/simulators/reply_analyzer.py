from app.domain.simulation import ModelReplySignal

_ANSWER_SIGNALS = ["因为", "来电是为了", "主要是", "我来说明", "简单说", "是这样的", "具体是"]


class RuleBasedReplyAnalyzer:
    def analyze(self, reply: str) -> ModelReplySignal:
        # answered_question: 模型有实质性解释，而非只是反问
        answered_question = any(kw in reply for kw in _ANSWER_SIGNALS) or (
            len(reply) > 20 and "？" not in reply
        )
        return ModelReplySignal(
            answered_question=answered_question,
            explained_reason=any(kw in reply for kw in ("因为", "来电是为了", "主要是")),
            followed_flow_step="step_2" if "收货时间" in reply or "方便收货" in reply else None,
            triggered_forbidden_action="一定送达" in reply or "保证送达" in reply,
            ignored_user_state="继续说一下" in reply,
        )
