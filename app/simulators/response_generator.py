from app.domain.simulation import UserIntent, UserProfile

# emotion → 各意图的兜底语气调整
_EMOTION_VARIANTS: dict[str, dict[str, str]] = {
    "resistant": {
        "say_busy":   "我在忙，有什么事直接说。",
        "ask_why":    "这有什么必要？",
        "refuse":     "我不想弄这个。",
        "interrupt":  "先停一下，说重点。",
        "say_unsure": "我再想想，不一定。",
    },
    "rejecting": {
        "say_busy":   "我很忙，你别打了。",
        "ask_why":    "没意义，我不想听。",
        "refuse":     "不做，挂了。",
        "interrupt":  "停，我要挂了。",
        "say_unsure": "不做。",
    },
}


class TemplateFirstResponseGenerator:
    def render(self, intent: UserIntent, profile: UserProfile, emotion: str = "neutral") -> str:
        variant = _EMOTION_VARIANTS.get(emotion, {})
        if intent.action in variant:
            return variant[intent.action]
        if intent.action == "say_busy":
            return "我现在有点忙，能快点说吗？"
        if intent.action == "ask_why":
            return "为什么必须这样？"
        if intent.action == "refuse":
            return "这个我不想做。"
        if intent.action == "interrupt":
            return "等一下，你先说重点。"
        if intent.action == "say_unsure":
            return "我现在还不太确定，可能明天下午吧。"
        if intent.action == "ask_task_specific_question" and intent.note:
            return intent.note
        if intent.action == "answer_slot":
            return "明天下午可以。"
        return "可以，你继续说。"
