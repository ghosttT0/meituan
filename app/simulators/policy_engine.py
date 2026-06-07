import random

from app.domain.simulation import ConversationState, ModelReplySignal, UserIntent, UserProfile
from app.simulators.question_pool import TaskQuestionPool


class UserPolicyEngine:
    def next_intent(
        self,
        primary_branch: str,
        state: ConversationState,
        signal: ModelReplySignal,
        question_pool: TaskQuestionPool | None = None,
        recent_questions: list[str] | None = None,
        profile: UserProfile | None = None,
        emotion: str = "neutral",
    ) -> UserIntent:
        # 情绪到 rejecting 时强制终止
        if emotion == "rejecting":
            return UserIntent(action="refuse", state="rejecting")

        if self._should_stop_questioning(primary_branch, state, profile):
            return UserIntent(action="answer_slot", state="cooperative")

        # 概率字段：随机触发打断/拒绝/追问行为，打破固定分支
        if profile:
            if profile.interruption_probability > 0 and random.random() < profile.interruption_probability:
                candidate = self._pick_question(question_pool, recent_questions or [], profile, ["objection", "step"])
                return UserIntent(action="interrupt", state="interrupting", note=candidate or "")
            if profile.reject_probability > 0 and random.random() < profile.reject_probability:
                return UserIntent(action="refuse", state="rejecting")
            if profile.question_probability > 0 and not signal.explained_reason:
                if random.random() < profile.question_probability:
                    candidate = self._pick_question(question_pool, recent_questions or [], profile, ["faq", "step"])
                    if candidate:
                        return UserIntent(action="ask_task_specific_question", state="questioning", note=candidate)

        if primary_branch == "busy":
            candidate = self._pick_question(question_pool, recent_questions or [], profile, ["objection"])
            return UserIntent(action="say_busy", state="busy", note=candidate or "")
        if primary_branch == "rejecting":
            candidate = self._pick_question(question_pool, recent_questions or [], profile, ["objection"])
            return UserIntent(action="refuse", state="rejecting", note=candidate or "")
        if primary_branch == "interrupting":
            candidate = self._pick_question(question_pool, recent_questions or [], profile, ["objection", "step"])
            return UserIntent(action="interrupt", state="interrupting", note=candidate or "")
        if primary_branch == "questioning" and not signal.explained_reason:
            candidate = self._pick_question(question_pool, recent_questions or [], profile, ["faq", "step"])
            if candidate:
                return UserIntent(action="ask_task_specific_question", state="questioning", note=candidate)
            return UserIntent(action="ask_why", state="questioning")
        if primary_branch == "hesitant":
            candidate = self._pick_question(question_pool, recent_questions or [], profile, ["faq", "step"])
            return UserIntent(action="say_unsure", state="hesitant", note=candidate or "")
        return UserIntent(action="answer_slot", state="cooperative")

    def _should_stop_questioning(
        self,
        primary_branch: str,
        state: ConversationState,
        profile: UserProfile | None,
    ) -> bool:
        if primary_branch != "questioning" or not profile:
            return False
        return state.turn_index >= max(profile.max_question_rounds, 0)

    def _pick_question(
        self,
        question_pool: TaskQuestionPool | None,
        recent_questions: list[str],
        profile: UserProfile | None,
        preferred_sources: list[str] | None = None,
    ) -> str | None:
        if not question_pool:
            return None
        order = preferred_sources or (profile.preferred_question_sources if profile else []) or ["faq", "step", "objection"]
        source_map = {
            "faq": question_pool.faq_questions,
            "step": question_pool.step_questions,
            "objection": question_pool.objection_questions,
        }
        preferred_tags = set(profile.preferred_question_tags if profile else [])
        candidates = []
        for source in order:
            candidates.extend(source_map.get(source, []))
        for source in ["faq", "step", "objection"]:
            for item in source_map.get(source, []):
                if item.prompt_text not in [c.prompt_text for c in candidates]:
                    candidates.append(item)

        tagged = (
            [item for item in candidates if self._matches_preferred_tags(item.prompt_text, item.tags, preferred_tags)]
            if preferred_tags else []
        )
        ordered = tagged + [item for item in candidates if item.prompt_text not in {c.prompt_text for c in tagged}]

        asked = set(recent_questions)
        for candidate in ordered:
            if candidate.prompt_text not in asked:
                return candidate.prompt_text
        return None  # 所有问题都问过了，不再重复

    def _matches_preferred_tags(self, prompt_text: str, explicit_tags: list[str], preferred_tags: set[str]) -> bool:
        return bool(preferred_tags.intersection(set(explicit_tags) | self._infer_tags_from_text(prompt_text)))

    def _infer_tags_from_text(self, prompt_text: str) -> set[str]:
        inferred: set[str] = set()
        if any(kw in prompt_text for kw in ["会怎么样", "怎么办", "影响", "做不到"]):
            inferred.update({"risk", "impact"})
        if "费用" in prompt_text or "更高" in prompt_text:
            inferred.update({"cost", "impact"})
        if any(kw in prompt_text for kw in ["区别", "差在哪", "有什么区别"]):
            inferred.update({"difference", "feature"})
        if any(kw in prompt_text for kw in ["没看到", "哪里开", "怎么操作", "怎么办"]):
            inferred.update({"operation", "visibility"})
        if any(kw in prompt_text for kw in ["忙", "说重点", "没空"]):
            inferred.update({"busy", "objection"})
        if any(kw in prompt_text for kw in ["退出", "不想继续"]):
            inferred.update({"exit", "objection"})
        return inferred
