import httpx


class ModelProbeService:
    def _headers(self, api_key: str, auth_type: str) -> dict:
        if auth_type == "bearer":
            return {"Authorization": f"Bearer {api_key}"}
        if auth_type == "api-key":
            return {"api-key": api_key}
        return {}

    async def list_models(self, api_url: str, api_key: str, auth_type: str = "bearer") -> dict:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    f"{api_url.rstrip('/')}/models",
                    headers=self._headers(api_key, auth_type),
                )
            response.raise_for_status()
            data = response.json()
            models = [item["id"] for item in data.get("data", []) if item.get("id")]
            return {"ok": True, "models": models, "error_message": ""}
        except Exception as exc:
            return {"ok": False, "models": [], "error_message": f"获取模型列表失败：{exc}"}

    async def check_model(
        self,
        api_url: str,
        api_key: str,
        model: str,
        protocol_mode: str = "auto",
        auth_type: str = "bearer",
    ) -> dict:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    f"{api_url.rstrip('/')}/chat/completions",
                    headers=self._headers(api_key, auth_type),
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": "你是测试助手。"},
                            {"role": "user", "content": "请回复：模型连接测试成功"},
                        ],
                        "max_tokens": 64,
                        "temperature": 0,
                    },
                )
            status_code = response.status_code
            response.raise_for_status()
            data = response.json()

            if protocol_mode in {"auto", "openai"} and data.get("choices"):
                reply = data["choices"][0]["message"]["content"]
                return {
                    "ok": True,
                    "status_code": status_code,
                    "protocol_type": "openai",
                    "reply_preview": reply[:200],
                    "error_message": "",
                }

            if protocol_mode in {"auto", "reply"} and data.get("reply"):
                reply = data["reply"]
                return {
                    "ok": True,
                    "status_code": status_code,
                    "protocol_type": "reply",
                    "reply_preview": reply[:200],
                    "error_message": "",
                }

            return {
                "ok": False,
                "status_code": status_code,
                "protocol_type": "unknown",
                "reply_preview": "",
                "error_message": "检测成功，但返回协议未识别。",
            }
        except Exception as exc:
            return {
                "ok": False,
                "status_code": 0,
                "protocol_type": "unknown",
                "reply_preview": "",
                "error_message": f"模型检测失败：{exc}",
            }
