"""用户情绪状态机。随对话进展和模型表现驱动情绪演变。"""
import random

from app.domain.simulation import ModelReplySignal, UserProfile

# 情绪状态顺序（从好到坏）
_EMOTION_LADDER = ["neutral", "skeptical", "resistant", "rejecting"]

# 各画像的情绪起点
_PROFILE_INITIAL_EMOTION: dict[str, str] = {
    "cooperative":  "neutral",
    "hesitant":     "skeptical",
    "questioning":  "skeptical",
    "rejecting":    "resistant",
    "busy":         "resistant",
    "interrupting": "skeptical",
}

# 每种情绪对应的 prompt 提示语（注入用户画像描述里）
EMOTION_PROMPTS: dict[str, str] = {
    "neutral":    "情绪平稳，可以正常交流。",
    "skeptical":  "开始产生疑虑，语气稍显迟疑，会追问细节。",
    "resistant":  "情绪明显抵触，回复简短，不愿继续深入。",
    "rejecting":  "情绪强烈排斥，倾向于挂断或直接拒绝。",
}


class EmotionEngine:
    def __init__(self, profile: UserProfile) -> None:
        initial = _PROFILE_INITIAL_EMOTION.get(profile.profile_id, "neutral")
        self._idx = _EMOTION_LADDER.index(initial)
        self._patience = profile.patience_level  # 0~1，越低越容易恶化

    @property
    def emotion(self) -> str:
        return _EMOTION_LADDER[self._idx]

    def step(self, signal: ModelReplySignal, turn_index: int) -> str:
        """根据模型回复信号推进情绪，返回当前情绪。"""
        if signal.triggered_forbidden_action:
            # 触发违规承诺 → 直接跳到排斥
            self._idx = len(_EMOTION_LADDER) - 1
        elif not signal.explained_reason and turn_index > 0:
            # 未解释原因 → 按耐心度概率恶化
            if random.random() > self._patience:
                self._idx = min(self._idx + 1, len(_EMOTION_LADDER) - 1)
        elif signal.explained_reason and signal.answered_question:
            # 充分解释 → 情绪改善（最多回到 neutral）
            self._idx = max(self._idx - 1, 0)
        return self.emotion
