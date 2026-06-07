from app.domain.conversation import Conversation
from app.domain.eval_spec import EvalSpec
from app.domain.evaluation_result import StepCandidate


class RequiredStepCandidateCollector:
    def collect(self, spec: EvalSpec, conversation: Conversation) -> list[StepCandidate]:
        candidates: list[StepCandidate] = []
        for step in spec.required_steps:
            turn_ids = self._match_turn_ids(step.id, step.name, step.evidence_requirement, conversation)
            candidates.append(
                StepCandidate(
                    step_id=step.id,
                    step_name=step.name,
                    candidate_turn_ids=turn_ids,
                    candidate_reason="candidate evidence recalled from conversation" if turn_ids else "no candidate evidence",
                    status="candidate" if turn_ids else "missing_candidate",
                )
            )
        return candidates

    def _match_turn_ids(
        self,
        step_id: str,
        step_name: str,
        evidence_requirement: str,
        conversation: Conversation,
    ) -> list[int]:
        matched: list[int] = []
        for turn in conversation.turns:
            if self._matches(step_id, step_name, evidence_requirement, turn.text):
                matched.append(turn.turn_id)
        return matched

    def _matches(self, step_id: str, step_name: str, evidence_requirement: str, text: str) -> bool:
        combined = f"{step_id} {step_name} {evidence_requirement}".lower()
        text_lower = text.lower()

        if "identity" in combined or "身份" in combined or "负责人" in combined:
            return any(keyword in text for keyword in ["请问您是", "负责人吗", "我是负责人", "是负责人", "请问是"])

        if "know" in combined or "知情" in combined or "知道" in combined:
            return any(keyword in text for keyword in ["知道", "知情", "没注意", "不太确定", "之前", "这个选项"])

        if "upgrade" in combined or "升级" in combined or "标准直播" in combined or "低延迟" in combined:
            return any(keyword in text for keyword in ["标准直播", "低延迟", "互动", "发布页", "分开展示", "更便宜", "略高"])

        seeds = [step_name, evidence_requirement]
        return any(seed and seed.lower() in text_lower for seed in seeds)
