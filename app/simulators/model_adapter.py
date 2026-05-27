import httpx
from typing import Protocol
from uuid import uuid4


class ModelAdapter(Protocol):
    async def start_session(self, config: dict) -> str:
        ...

    async def send_user_message(self, message: str) -> str:
        ...

    async def end_session(self) -> None:
        ...


class MockModelAdapter:
    def __init__(self) -> None:
        self.session_id = ""
        self.history: list[dict] = []

    async def start_session(self, config: dict) -> str:
        self.session_id = f"mock_{uuid4().hex[:8]}"
        self.history = []
        return self.session_id

    async def send_user_message(self, message: str) -> str:
        self.history.append({"speaker": "user", "text": message})
        if "为什么" in message:
            reply = "因为这次主要是确认安排，避免耽误配送。"
        elif "忙" in message:
            reply = "我就简短说一下，主要想确认您明天下午是否方便。"
        else:
            reply = "您好，请问您明天下午方便收货吗？"
        self.history.append({"speaker": "assistant", "text": reply})
        return reply

    async def end_session(self) -> None:
        self.history = []


class HttpModelAdapter:
    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint
        self.request_url = self._normalize_openai_endpoint(endpoint)
        self.session_id = ""
        self.history: list[dict] = []

    def build_payload(
        self, session_id: str, history: list[dict], task_instruction_text: str
    ) -> dict:
        if getattr(self, "protocol_mode", "reply") == "openai":
            messages = []
            if task_instruction_text:
                messages.append({"role": "system", "content": task_instruction_text})
            for item in history:
                speaker = item.get("speaker", "")
                role = "assistant" if speaker in {"assistant", "agent"} else "user"
                messages.append({"role": role, "content": item.get("text", "")})
            return {
                "model": getattr(self, "model", ""),
                "messages": messages,
            }
        return {
            "session_id": session_id,
            "model": getattr(self, "model", ""),
            "task_instruction": task_instruction_text,
            "system_prompt": task_instruction_text,
            "history": history,
        }

    async def start_session(self, config: dict) -> str:
        self.session_id = config.get("session_id", f"http_{uuid4().hex[:8]}")
        self.task_instruction_text = config.get("task_instruction_text", "")
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "")
        self.auth_type = config.get("auth_type", "bearer")
        self.protocol_mode = self._resolve_protocol_mode(config.get("protocol_mode", "auto"))
        self.request_url = (
            self.endpoint
            if self.protocol_mode == "reply"
            else self._normalize_openai_endpoint(self.endpoint)
        )
        self.history = []
        return self.session_id

    async def send_user_message(self, message: str) -> str:
        self.history.append({"speaker": "user", "text": message})
        headers = (
            {"Authorization": f"Bearer {self.api_key}"}
            if self.auth_type == "bearer" and self.api_key
            else ({"api-key": self.api_key} if self.auth_type == "api-key" and self.api_key else {})
        )
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                self.request_url,
                headers=headers,
                json=self.build_payload(self.session_id, self.history, self.task_instruction_text),
            )
        response.raise_for_status()
        data = response.json()
        reply = (
            (data.get("choices") or [{}])[0].get("message", {}).get("content")
            if self.protocol_mode == "openai"
            else None
        ) or data.get("reply") or data.get("content") or data.get("message")
        if not reply:
            raise KeyError("reply")
        self.history.append({"speaker": "assistant", "text": reply})
        return reply

    async def end_session(self) -> None:
        self.history = []

    def _normalize_openai_endpoint(self, endpoint: str) -> str:
        trimmed = endpoint.rstrip("/")
        if trimmed.endswith("/chat/completions"):
            return trimmed
        return f"{trimmed}/chat/completions"

    def _resolve_protocol_mode(self, protocol_mode: str) -> str:
        if protocol_mode in {"openai", "reply"}:
            return protocol_mode
        trimmed = self.endpoint.rstrip("/").lower()
        if trimmed.endswith("/chat/completions") or trimmed.endswith("/v1"):
            return "openai"
        return "reply"
