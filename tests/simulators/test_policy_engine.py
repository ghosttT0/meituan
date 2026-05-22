from app.domain.simulation import ConversationState, ModelReplySignal
from app.simulators.policy_engine import UserPolicyEngine


def test_policy_engine_returns_busy_intent_for_busy_branch() -> None:
    engine = UserPolicyEngine()
    state = ConversationState(current_state="init", turn_index=0)
    signal = ModelReplySignal(answered_question=False, explained_reason=False)

    intent = engine.next_intent(primary_branch="busy", state=state, signal=signal)

    assert intent.state == "busy"
    assert intent.action == "say_busy"


def test_policy_engine_returns_questioning_intent_when_reason_missing() -> None:
    engine = UserPolicyEngine()
    state = ConversationState(current_state="listening", turn_index=1)
    signal = ModelReplySignal(answered_question=False, explained_reason=False)

    intent = engine.next_intent(primary_branch="questioning", state=state, signal=signal)

    assert intent.state == "questioning"
    assert intent.action == "ask_why"
