from typing import Protocol


class LLMAdapter(Protocol):
    def score_dimension(self, dimension_id: str, rubric: list[str], conversation_text: str) -> dict:
        ...


class FakeLLMAdapter:
    def score_dimension(self, dimension_id: str, rubric: list[str], conversation_text: str) -> dict:
        hit = "确认" in conversation_text or "来电" in conversation_text
        return {
            "dimension_id": dimension_id,
            "score": 0.9 if hit else 0.3,
            "confidence": 0.8 if hit else 0.5,
            "reason": "rubric hit" if hit else "rubric weak",
            "evidence_turn_ids": [1] if hit else [],
        }
