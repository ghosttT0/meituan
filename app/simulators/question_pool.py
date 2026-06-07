import random

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


# 每类触发场景提供多条变体，随机选一条
_VARIANTS: dict[str, list[tuple[str, list[str]]]] = {
    "exit": [
        ("那我想退出的话怎么操作？", ["exit", "operation"]),
        ("如果我不想做了，怎么退出？", ["exit", "operation"]),
        ("我要怎么退出这个？", ["exit", "operation"]),
    ],
    "quota_risk": [
        ("如果我做不到要求单量会怎么样？", ["risk", "impact"]),
        ("万一我今天跑不够单会有什么后果？", ["risk", "impact"]),
        ("完不成要求的话会影响什么？", ["risk", "impact"]),
    ],
    "cost": [
        ("那费用会不会更高？", ["cost", "impact"]),
        ("这个升级之后费用有变化吗？", ["cost", "impact"]),
        ("需要额外付钱吗？", ["cost", "impact"]),
    ],
    "live_diff": [
        ("低延迟直播和标准直播差在哪？", ["difference", "feature"]),
        ("这两种直播方式到底有什么区别？", ["difference", "feature"]),
        ("你先说一下这两个有啥不一样。", ["difference", "feature"]),
    ],
    "visibility": [
        ("如果我没看到这个选项，要去哪里开？", ["operation", "visibility"]),
        ("我现在没看到这个选项怎么办？", ["visibility", "operation"]),
        ("这个在哪里设置？我找不到。", ["visibility", "operation"]),
    ],
    "delivery_risk": [
        ("我今天要是开始不了配送会怎么样？", ["risk", "impact"]),
        ("如果今天我不能出发会影响合同吗？", ["risk", "impact"]),
        ("开始不了配送的话有什么后果？", ["risk", "impact"]),
    ],
    "busy": [
        ("我现在有点忙，你能说重点吗？", ["busy", "objection"]),
        ("我在忙，快点说。", ["busy", "objection"]),
        ("长话短说，重点是什么？", ["busy", "objection"]),
    ],
    "authority": [
        ("这个你能直接帮我处理吗？", ["objection", "operation"]),
        ("这不是你们定的吗？你能不能直接改？", ["objection", "authority"]),
        ("你帮我处理掉，不用我自己弄。", ["objection", "authority"]),
    ],
    "quit_intent": [
        ("那我现在不想继续了怎么办？", ["exit", "objection"]),
        ("我不想参加这个了，怎么退？", ["exit", "objection"]),
        ("可以不做吗？怎么取消？", ["exit", "objection"]),
    ],
    # uninformed 画像专属：困惑型
    "uninformed_contract": [
        ("我当时有签过这个合同吗？我不太记得了。", ["uninformed", "operation"]),
        ("你说的这个合同我没什么印象，能确认一下吗？", ["uninformed", "operation"]),
        ("这个我之前好像没操作过，是新的吗？", ["uninformed", "operation"]),
    ],
    "uninformed_system": [
        ("这个系统我没见过，你说的在哪里？", ["uninformed", "visibility"]),
        ("我不知道你说的这个是什么，能说清楚点吗？", ["uninformed", "operation"]),
        ("我平时不怎么用这个，你说的步骤我没找到。", ["uninformed", "visibility"]),
    ],
}

# task_type 后备问题（问题池为空时兜底）
_FALLBACK_BY_TASK_TYPE: dict[str, list[tuple[str, list[str], str]]] = {
    "rider": [
        ("今天跑不了单会影响我的合同吗？", ["risk", "impact"], "faq"),
        ("我现在没有接到派单，是正常的吗？", ["visibility", "operation"], "step"),
        ("我能直接退出飞毛腿吗？", ["exit", "objection"], "objection"),
    ],
    "course_live": [
        ("这个升级我必须做吗？不做会怎样？", ["risk", "impact"], "faq"),
        ("低延迟直播费用比标准直播贵多少？", ["cost", "impact"], "faq"),
        ("我们机构现在用的是哪种直播？", ["uninformed", "operation"], "step"),
    ],
    "general": [
        ("这个我必须配合吗？不做有什么影响？", ["risk", "impact"], "faq"),
        ("你说的这个我不太清楚，能解释一下吗？", ["uninformed", "operation"], "step"),
        ("这件事我能以后再处理吗？", ["exit", "objection"], "objection"),
    ],
}


def _pick(key: str) -> TaskQuestionItem:
    variants = _VARIANTS[key]
    text, tags = random.choice(variants)
    return TaskQuestionItem(source=key, prompt_text=text, tags=tags)


class TaskQuestionPoolBuilder:
    def build(self, spec: EvalSpec) -> TaskQuestionPool:
        faq_questions: list[TaskQuestionItem] = []
        step_questions: list[TaskQuestionItem] = []
        objection_questions: list[TaskQuestionItem] = []

        for item in spec.faq_items:
            text = item.raw_text
            if "退出" in text:
                faq_questions.append(_pick("exit"))
            if "单日合同" in text or "多日合同" in text or "单量" in text:
                faq_questions.append(_pick("quota_risk"))
            if "低延迟直播" in text and "费用" in text:
                faq_questions.append(_pick("cost"))
            if "低延迟直播" in text:
                faq_questions.append(_pick("live_diff"))
            if "第三方系统" in text or "直播平台" in text or "选项" in text:
                faq_questions.append(_pick("visibility"))

        for step in spec.flow_steps:
            text = step.raw_text + step.title
            if "配送" in text or "开始配送" in text:
                step_questions.append(_pick("delivery_risk"))
            if "可见" in text or "前端" in text or "选项" in text:
                step_questions.append(_pick("visibility"))
            if "区别" in text:
                step_questions.append(_pick("live_diff"))

        for item in spec.constraint_items:
            text = item.raw_text
            if "挂断" in text or "忙" in text:
                objection_questions.append(_pick("busy"))
            if "超出职责范围" in text:
                objection_questions.append(_pick("authority"))

        for text in spec.fallback_policy:
            if "退出" in text:
                objection_questions.append(_pick("quit_intent"))
            if "超出职责范围" in text:
                objection_questions.append(_pick("authority"))

        # uninformed 画像专属问题（始终注入）
        faq_questions.append(_pick("uninformed_contract"))
        step_questions.append(_pick("uninformed_system"))

        pool = TaskQuestionPool(
            faq_questions=self._unique(faq_questions),
            step_questions=self._unique(step_questions),
            objection_questions=self._unique(objection_questions),
        )

        # 始终追加 task_type 后备问题，保证泛化能力（去重后不会重复）
        pool = self._apply_fallback(pool, spec.task_type)

        return pool

    def _apply_fallback(self, pool: TaskQuestionPool, task_type: str) -> TaskQuestionPool:
        fallbacks = _FALLBACK_BY_TASK_TYPE.get(task_type, _FALLBACK_BY_TASK_TYPE["general"])
        for text, tags, bucket in fallbacks:
            item = TaskQuestionItem(source="fallback", prompt_text=text, tags=tags)
            if bucket == "faq":
                pool.faq_questions.append(item)
            elif bucket == "step":
                pool.step_questions.append(item)
            else:
                pool.objection_questions.append(item)
        return pool

    def _unique(self, items: list[TaskQuestionItem]) -> list[TaskQuestionItem]:
        seen: set[str] = set()
        result = []
        for item in items:
            if item.prompt_text not in seen:
                seen.add(item.prompt_text)
                result.append(item)
        return result
