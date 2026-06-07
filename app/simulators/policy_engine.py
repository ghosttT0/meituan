from app.domain.simulation import ConversationState, ModelReplySignal, UserIntent
from app.simulators.question_pool import TaskQuestionPool
from app.domain.simulation import UserProfile


class UserPolicyEngine:
    def next_intent(
        self,
        primary_branch: str,
        state: ConversationState,
        signal: ModelReplySignal,
        question_pool: TaskQuestionPool | None = None,
        recent_questions: list[str] | None = None,
        profile: UserProfile | None = None,
    ) -> UserIntent:
        if self._should_stop_questioning(primary_branch, state, profile):
            return UserIntent(action="answer_slot", state="cooperative")
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
                return UserIntent(
                    action="ask_task_specific_question",
                    state="questioning",
                    note=candidate,
                )
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
                if item.prompt_text not in [candidate.prompt_text for candidate in candidates]:
                    candidates.append(item)

        tagged_candidates = (
            [item for item in candidates if self._matches_preferred_tags(item.prompt_text, item.tags, preferred_tags)]
            if preferred_tags
            else []
        )
        ordered_candidates = tagged_candidates + [
            item for item in candidates if item.prompt_text not in {candidate.prompt_text for candidate in tagged_candidates}
        ]

        for candidate in ordered_candidates:
            if candidate.prompt_text not in recent_questions[-3:]:
                return candidate.prompt_text
        return ordered_candidates[0].prompt_text if ordered_candidates else None

    def _matches_preferred_tags(
        self,
        prompt_text: str,
        explicit_tags: list[str],
        preferred_tags: set[str],
    ) -> bool:
        all_tags = set(explicit_tags) | self._infer_tags_from_text(prompt_text)
        return bool(preferred_tags.intersection(all_tags))

    def _infer_tags_from_text(self, prompt_text: str) -> set[str]:
        inferred: set[str] = set()
        if any(keyword in prompt_text for keyword in ["会怎么样", "怎么办", "影响", "做不到"]):
            inferred.update({"risk", "impact"})
        if "费用" in prompt_text or "更高" in prompt_text:
            inferred.update({"cost", "impact"})
        if any(keyword in prompt_text for keyword in ["区别", "差在哪", "有什么区别"]):
            inferred.update({"difference", "feature"})
        if any(keyword in prompt_text for keyword in ["没看到", "哪里开", "怎么操作", "怎么办"]):
            inferred.update({"operation", "visibility"})
        if any(keyword in prompt_text for keyword in ["忙", "说重点", "没空"]):
            inferred.update({"busy", "objection"})
        if any(keyword in prompt_text for keyword in ["退出", "不想继续"]):
            inferred.update({"exit", "objection"})
        return inferred
