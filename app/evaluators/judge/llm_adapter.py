import json
import re
from typing import Protocol

from openai import OpenAI

from app.core.config import get_settings


class LLMAdapter(Protocol):
    def score_dimension(self, dimension_id: str, rubric: list[str], conversation_text: str) -> dict:
        ...


DIMENSION_LABELS = {
    "task_focus": "任务聚焦度",
    "explanation_quality": "解释充分性",
}


class FakeLLMAdapter:
    def score_dimension(self, dimension_id: str, rubric: list[str], conversation_text: str) -> dict:
        hit = "确认" in conversation_text or "来电" in conversation_text
        return {
            "dimension_id": dimension_id,
            "score": 0.9 if hit else 0.3,
            "confidence": 0.8 if hit else 0.5,
            "reason": "命中评分标准" if hit else "未充分命中评分标准",
            "evidence_turn_ids": [1] if hit else [],
        }


class OpenAILLMAdapter:
    def __init__(self, client: OpenAI | None = None) -> None:
        settings = get_settings()
        if client is None:
            self.client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            )
        else:
            self.client = client
        self.model = settings.openai_model

    def score_dimension(self, dimension_id: str, rubric: list[str], conversation_text: str) -> dict:
        rubric_text = "\n".join(f"- {item}" for item in rubric)
        dimension_label = DIMENSION_LABELS.get(dimension_id, dimension_id)

        prompt = f"""你是一个对话质量评估专家。请根据以下中文评分标准对对话进行评分。

评分维度：{dimension_label}

评分标准：
{rubric_text}

对话内容：
{conversation_text}

请严格按照以下 JSON 格式返回评分结果：
{{
  "dimension_id": "{dimension_id}",
  "score": <0.0-1.0之间的分数>,
  "confidence": <0.0-1.0之间的置信度>,
  "reason": "<中文评分理由>",
  "evidence_turn_ids": [<相关轮次编号列表>]
}}

只返回 JSON，不要返回任何额外说明。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的对话质量评估专家，所有输出都必须使用中文。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("empty response")

            result = json.loads(self._extract_json(content))
            return {
                "dimension_id": result.get("dimension_id", dimension_id),
                "score": float(result.get("score", 0.5)),
                "confidence": float(result.get("confidence", 0.5)),
                "reason": result.get("reason", "未返回评分理由"),
                "evidence_turn_ids": result.get("evidence_turn_ids", []),
            }

        except Exception as e:
            return {
                "dimension_id": dimension_id,
                "score": 0.5,
                "confidence": 0.3,
                "reason": f"LLM评估失败：{str(e)}",
                "evidence_turn_ids": [],
            }

    def _extract_json(self, content: str) -> str:
        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, re.DOTALL)
        if fenced:
            return fenced.group(1).strip()
        return content.strip()
