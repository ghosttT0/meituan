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
        self.session_id = ""
        self.history: list[dict] = []

    def build_payload(self, session_id: str, history: list[dict]) -> dict:
        return {"session_id": session_id, "history": history}

    async def start_session(self, config: dict) -> str:
        self.session_id = config.get("session_id", f"http_{uuid4().hex[:8]}")
        self.history = []
        return self.session_id

    async def send_user_message(self, message: str) -> str:
        self.history.append({"speaker": "user", "text": message})
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                self.endpoint, json=self.build_payload(self.session_id, self.history)
            )
        response.raise_for_status()
        data = response.json()
        reply = data["reply"]
        self.history.append({"speaker": "assistant", "text": reply})
        return reply

    async def end_session(self) -> None:
        self.history = []
