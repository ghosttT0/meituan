from app.domain.simulation import UserIntent, UserProfile


class TemplateFirstResponseGenerator:
    def render(self, intent: UserIntent, profile: UserProfile) -> str:
        if intent.action == "say_busy":
            return "我现在有点忙，能快点说吗？"
        if intent.action == "ask_why":
            return "为什么必须这样？"
        if intent.action == "refuse":
            return "这个我不想做。"
        if intent.action == "interrupt":
            return "等一下，你先说重点。"
        if intent.action == "say_unsure":
            return "我现在还不太确定。"
        return "可以，你继续说。"
