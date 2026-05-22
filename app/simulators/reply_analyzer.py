from app.domain.simulation import ModelReplySignal


class RuleBasedReplyAnalyzer:
    def analyze(self, reply: str) -> ModelReplySignal:
        return ModelReplySignal(
            answered_question="？" not in reply,
            explained_reason=("因为" in reply) or ("来电是为了" in reply) or ("主要是" in reply),
            followed_flow_step="step_2" if "收货时间" in reply or "方便收货" in reply else None,
            triggered_forbidden_action=("一定送达" in reply) or ("保证送达" in reply),
            ignored_user_state=("继续说一下" in reply),
        )
