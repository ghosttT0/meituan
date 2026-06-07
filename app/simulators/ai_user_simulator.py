import json
import re

from openai import OpenAI

from app.core.config import get_settings
from app.domain.simulation import SimulatedUserReply


class OpenAIUserSimulatorAdapter:
    def __init__(self, client: OpenAI | None = None) -> None:
        settings = get_settings()
        self.client = client or OpenAI(
            api_key=settings.simulator_api_key or settings.openai_api_key,
            base_url=settings.simulator_base_url or settings.openai_base_url,
        )
        self.model = settings.simulator_model or settings.openai_model

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
        except Exception as exc:
            # 把失败原因暴露出去，让调用方记录到 debug_logs
            raise RuntimeError(f"用户模拟器调用失败：{exc}") from exc

    def _extract_json(self, content: str) -> str:
        # 优先匹配代码块
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if fenced:
            return fenced.group(1).strip()
        # 兜底：找第一个 { 到最后一个 }
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            return content[start : end + 1]
        return content.strip()
