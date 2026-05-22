from app.domain.simulation import ConversationState, ModelReplySignal, UserIntent


class UserPolicyEngine:
    def next_intent(
        self, primary_branch: str, state: ConversationState, signal: ModelReplySignal
    ) -> UserIntent:
        if primary_branch == "busy":
            return UserIntent(action="say_busy", state="busy")
        if primary_branch == "rejecting":
            return UserIntent(action="refuse", state="rejecting")
        if primary_branch == "interrupting":
            return UserIntent(action="interrupt", state="interrupting")
        if primary_branch == "questioning" and not signal.explained_reason:
            return UserIntent(action="ask_why", state="questioning")
        if primary_branch == "hesitant":
            return UserIntent(action="say_unsure", state="hesitant")
        return UserIntent(action="answer_slot", state="cooperative")
