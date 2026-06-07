from pydantic import BaseModel, Field

from app.domain.eval_spec import EvalSpec


class TaskQuestionItem(BaseModel):
    source: str
    prompt_text: str
    tags: list[str] = Field(default_factory=list)


class TaskQuestionPool(BaseModel):
    faq_questions: list[TaskQuestionItem] = Field(default_factory=list)
    step_questions: list[TaskQuestionItem] = Field(default_factory=list)
    objection_questions: list[TaskQuestionItem] = Field(default_factory=list)


class TaskQuestionPoolBuilder:
    def build(self, spec: EvalSpec) -> TaskQuestionPool:
        faq_questions = []
        for item in spec.faq_items:
            text = item.raw_text
            if "退出" in text:
                faq_questions.append(TaskQuestionItem(source=item.faq_id, prompt_text="那我想退出的话怎么操作？", tags=["exit", "operation"]))
            if "单日合同" in text or "多日合同" in text:
                faq_questions.append(TaskQuestionItem(source=item.faq_id, prompt_text="如果我做不到要求单量会怎么样？", tags=["risk", "impact"]))
            if "低延迟直播" in text and "费用" in text:
                faq_questions.append(TaskQuestionItem(source=item.faq_id, prompt_text="那费用会不会更高？", tags=["cost", "impact"]))
            if "低延迟直播" in text:
                faq_questions.append(TaskQuestionItem(source=item.faq_id, prompt_text="低延迟直播和标准直播差在哪？", tags=["difference", "feature"]))
            if "第三方系统" in text or "直播平台" in text:
                faq_questions.append(TaskQuestionItem(source=item.faq_id, prompt_text="如果我没看到这个选项，要去哪里开？", tags=["operation", "visibility"]))

        step_questions = []
        for step in spec.flow_steps:
            text = step.raw_text + step.title
            if "开始配送" in text or "配送" in text:
                step_questions.append(TaskQuestionItem(source=step.step_id, prompt_text="我今天要是开始不了配送会怎么样？", tags=["risk", "impact"]))
            if "可见" in text or "前端" in text or "选项" in text:
                step_questions.append(TaskQuestionItem(source=step.step_id, prompt_text="我现在没看到这个选项怎么办？", tags=["visibility", "operation"]))
            if "区别" in text:
                step_questions.append(TaskQuestionItem(source=step.step_id, prompt_text="你先说下这两个到底有什么区别？", tags=["difference", "feature"]))

        objection_questions = []
        for item in spec.constraint_items:
            text = item.raw_text
            if "挂断" in text or "忙" in text:
                objection_questions.append(TaskQuestionItem(source=item.constraint_id, prompt_text="我现在有点忙，你能说重点吗？", tags=["busy", "objection"]))
            if "超出职责范围" in text:
                objection_questions.append(TaskQuestionItem(source=item.constraint_id, prompt_text="这个你能直接帮我处理吗？", tags=["objection", "operation"]))

        for text in spec.fallback_policy:
            if "退出" in text:
                objection_questions.append(TaskQuestionItem(source="fallback", prompt_text="那我现在不想继续了怎么办？", tags=["exit", "objection"]))
            if "超出职责范围" in text:
                objection_questions.append(TaskQuestionItem(source="fallback", prompt_text="这不是你们定的吗？你能不能直接改？", tags=["objection", "authority"]))

        return TaskQuestionPool(
            faq_questions=self._unique(faq_questions),
            step_questions=self._unique(step_questions),
            objection_questions=self._unique(objection_questions),
        )

    def _unique(self, items: list[TaskQuestionItem]) -> list[TaskQuestionItem]:
        seen = set()
        result = []
        for item in items:
            if item.prompt_text in seen:
                continue
            seen.add(item.prompt_text)
            result.append(item)
        return result
