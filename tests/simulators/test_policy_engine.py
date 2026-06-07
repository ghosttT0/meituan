from app.domain.simulation import ConversationState, ModelReplySignal, UserProfile
from app.simulators.question_pool import TaskQuestionItem, TaskQuestionPool
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


def test_policy_engine_picks_task_specific_question_for_questioning_branch() -> None:
    engine = UserPolicyEngine()
    state = ConversationState(current_state="questioning", turn_index=1)
    signal = ModelReplySignal(answered_question=False, explained_reason=False)
    pool = TaskQuestionPool(
        faq_questions=[TaskQuestionItem(source="faq_1", prompt_text="低延迟直播和标准直播差在哪？")],
        step_questions=[TaskQuestionItem(source="step_1", prompt_text="我现在没看到这个选项怎么办？")],
        objection_questions=[],
    )

    intent = engine.next_intent(
        primary_branch="questioning",
        state=state,
        signal=signal,
        question_pool=pool,
        recent_questions=[],
    )

    assert intent.state == "questioning"
    assert intent.action == "ask_task_specific_question"
    assert "低延迟直播" in intent.note or "选项" in intent.note


def test_policy_engine_prefers_objection_pool_for_busy_profile() -> None:
    engine = UserPolicyEngine()
    state = ConversationState(current_state="busy", turn_index=1)
    signal = ModelReplySignal(answered_question=False, explained_reason=False)
    pool = TaskQuestionPool(
        faq_questions=[TaskQuestionItem(source="faq_1", prompt_text="低延迟直播和标准直播差在哪？")],
        step_questions=[TaskQuestionItem(source="step_1", prompt_text="我现在没看到这个选项怎么办？")],
        objection_questions=[TaskQuestionItem(source="obj_1", prompt_text="我现在很忙，你直接说重点。")],
    )
    profile = UserProfile(
        profile_id="busy",
        name="忙碌型",
        cooperation_level=0.4,
        patience_level=0.2,
        preferred_question_sources=["objection"],
        max_objection_rounds=2,
    )

    intent = engine.next_intent(
        primary_branch="busy",
        state=state,
        signal=signal,
        question_pool=pool,
        recent_questions=[],
        profile=profile,
    )

    assert intent.state == "busy"
    assert "忙" in intent.note or intent.action == "say_busy"


def test_policy_engine_degrades_after_question_round_limit() -> None:
    engine = UserPolicyEngine()
    state = ConversationState(current_state="questioning", turn_index=3)
    signal = ModelReplySignal(answered_question=False, explained_reason=False)
    pool = TaskQuestionPool(
        faq_questions=[TaskQuestionItem(source="faq_1", prompt_text="低延迟直播和标准直播差在哪？")],
        step_questions=[TaskQuestionItem(source="step_1", prompt_text="我现在没看到这个选项怎么办？")],
        objection_questions=[],
    )
    profile = UserProfile(
        profile_id="questioning",
        name="追问型",
        cooperation_level=0.6,
        patience_level=0.7,
        preferred_question_sources=["faq", "step"],
        max_question_rounds=1,
    )

    intent = engine.next_intent(
        primary_branch="questioning",
        state=state,
        signal=signal,
        question_pool=pool,
        recent_questions=["低延迟直播和标准直播差在哪？"],
        profile=profile,
    )

    assert intent.action == "answer_slot"
    assert intent.state == "cooperative"


def test_policy_engine_prefers_risk_questions_for_hesitant_profile() -> None:
    engine = UserPolicyEngine()
    state = ConversationState(current_state="hesitant", turn_index=1)
    signal = ModelReplySignal(answered_question=False, explained_reason=False)
    pool = TaskQuestionPool(
        faq_questions=[TaskQuestionItem(source="faq_1", prompt_text="低延迟直播和标准直播差在哪？")],
        step_questions=[TaskQuestionItem(source="step_1", prompt_text="如果我做不到要求单量会怎么样？")],
        objection_questions=[TaskQuestionItem(source="obj_1", prompt_text="我现在很忙，你直接说重点。")],
    )
    profile = UserProfile(
        profile_id="hesitant",
        name="犹豫型",
        cooperation_level=0.5,
        patience_level=0.7,
        preferred_question_sources=["faq", "step"],
        preferred_question_tags=["risk", "impact", "cost"],
        max_question_rounds=2,
    )

    intent = engine.next_intent(
        primary_branch="hesitant",
        state=state,
        signal=signal,
        question_pool=pool,
        recent_questions=[],
        profile=profile,
    )

    assert intent.action == "say_unsure"
    assert "怎么样" in intent.note or "影响" in intent.note or "费用" in intent.note
