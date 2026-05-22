import json
import re

from openai import OpenAI

from app.core.config import get_settings
from app.domain.simulation import SimulatedUserReply


class OpenAIUserSimulatorAdapter:
    def __init__(self, client: OpenAI | None = None) -> None:
        settings = get_settings()
        self.client = client or OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self.model = settings.openai_model

    def generate_turn(self, prompt: str) -> SimulatedUserReply | None:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是外呼任务中的真实用户，只能扮演用户，用中文返回结构化 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=300,
            )
            content = response.choices[0].message.content
            if not content:
                return None
            data = json.loads(self._extract_json(content))
            return SimulatedUserReply(
                state=data["state"],
                intent=data["intent"],
                reply=data["reply"],
                should_end=bool(data.get("should_end", False)),
            )
        except Exception:
            return None

    def _extract_json(self, content: str) -> str:
        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, re.DOTALL)
        if fenced:
            return fenced.group(1).strip()
        return content.strip()
