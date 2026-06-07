import json
import re
from typing import Protocol

from openai import OpenAI

from app.core.config import get_settings


class LLMAdapter(Protocol):
    def score_dimension(
        self,
        dimension_id: str,
        rubric: list[str],
        conversation_text: str,
        judge_role: str = "general",
    ) -> dict:
        ...

    def review_scenario(
        self,
        rule_id: str,
        criteria: list[str],
        conversation_text: str,
        baseline_passed: bool,
        baseline_reason: str,
        judge_role: str = "general",
    ) -> dict:
        ...

    def review_required_step(
        self,
        step_id: str,
        step_name: str,
        evidence_requirement: str,
        conversation_text: str,
        candidate_turn_ids: list[int],
        candidate_reason: str,
        judge_role: str = "general",
    ) -> dict:
        ...


DIMENSION_LABELS = {
    "task_focus": "任务聚焦度",
    "explanation_quality": "解释充分性",
}

JUDGE_PERSONAS = {
    "general": "综合评估对话质量，兼顾任务达成、表达质量与证据充分性。",
    "task_alignment": "偏重任务对齐、流程推进、问题是否跑偏。",
    "experience_risk": "偏重用户体验、解释充分性、误导与越权风险。",
    "arbitrator": "作为仲裁评审，在主评委分歧时给出更稳健的最终判断。",
}


class FakeLLMAdapter:
    def score_dimension(
        self,
        dimension_id: str,
        rubric: list[str],
        conversation_text: str,
        judge_role: str = "general",
    ) -> dict:
        hit = "确认" in conversation_text or "来电" in conversation_text
        return {
            "dimension_id": dimension_id,
            "score": 0.9 if hit else 0.3,
            "confidence": 0.8 if hit else 0.5,
            "reason": "命中评分标准" if hit else "未充分命中评分标准",
            "evidence_turn_ids": [1] if hit else [],
            "status": "ok",
        }

    def review_scenario(
        self,
        rule_id: str,
        criteria: list[str],
        conversation_text: str,
        baseline_passed: bool,
        baseline_reason: str,
        judge_role: str = "general",
    ) -> dict:
        return {
            "rule_id": rule_id,
            "passed": baseline_passed,
            "confidence": 0.75,
            "reason": baseline_reason,
            "evidence_turn_ids": [1] if baseline_passed else [],
            "status": "ok",
        }

    def review_required_step(
        self,
        step_id: str,
        step_name: str,
        evidence_requirement: str,
        conversation_text: str,
        candidate_turn_ids: list[int],
        candidate_reason: str,
        judge_role: str = "general",
    ) -> dict:
        completed = bool(candidate_turn_ids)
        return {
            "step_id": step_id,
            "step_name": step_name,
            "completed": completed,
            "confidence": 0.8 if completed else 0.45,
            "reason": candidate_reason if completed else "未找到足够候选证据",
            "evidence_turn_ids": candidate_turn_ids,
            "status": "ok" if completed else "needs_review",
        }


class OpenAILLMAdapter:
    def __init__(self, client: OpenAI | None = None) -> None:
        settings = get_settings()
        self.client = client or OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            max_retries=0,
            timeout=8.0,
        )
        self.model = settings.openai_model

    def score_dimension(
        self,
        dimension_id: str,
        rubric: list[str],
        conversation_text: str,
        judge_role: str = "general",
    ) -> dict:
        rubric_text = "\n".join(f"- {item}" for item in rubric)
        dimension_label = DIMENSION_LABELS.get(dimension_id, dimension_id)
        persona_text = JUDGE_PERSONAS.get(judge_role, JUDGE_PERSONAS["general"])
        prompt = f"""你是一个对话质量评估专家。请根据以下中文评分标准对对话进行评分。
评审角色：{persona_text}
评分维度：{dimension_label}

评分标准：
{rubric_text}

对话内容：
{conversation_text}

请严格按以下 JSON 格式返回评分结果：
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
            result = self._safe_parse_json(content)
            return {
                "dimension_id": result.get("dimension_id", dimension_id),
                "score": float(result.get("score", 0.5)),
                "confidence": float(result.get("confidence", 0.5)),
                "reason": result.get("reason", "未返回评分理由"),
                "evidence_turn_ids": result.get("evidence_turn_ids", []),
                "status": "ok",
            }
        except Exception as exc:
            return {
                "dimension_id": dimension_id,
                "score": 0.5,
                "confidence": 0.3,
                "reason": f"LLM评估失败：{self._normalize_error_message(str(exc))}",
                "evidence_turn_ids": [],
                "status": "fallback",
            }

    def review_scenario(
        self,
        rule_id: str,
        criteria: list[str],
        conversation_text: str,
        baseline_passed: bool,
        baseline_reason: str,
        judge_role: str = "general",
    ) -> dict:
        criteria_text = "\n".join(f"- {item}" for item in criteria)
        persona_text = JUDGE_PERSONAS.get(judge_role, JUDGE_PERSONAS["general"])
        prompt = f"""你是一个对话质量评估专家。请复核下面这个场景性判断。
评审角色：{persona_text}
规则 ID：{rule_id}

复核标准：
{criteria_text}

规则引擎基线结论：
- passed: {str(baseline_passed).lower()}
- reason: {baseline_reason}

对话内容：
{conversation_text}

请只返回 JSON：
{{
  "rule_id": "{rule_id}",
  "passed": <true/false>,
  "confidence": <0.0-1.0>,
  "reason": "<中文理由>",
  "evidence_turn_ids": [<相关轮次编号>]
}}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的对话质量评估专家，所有输出都必须使用中文。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=400,
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("empty response")
            result = self._safe_parse_json(content)
            return {
                "rule_id": result.get("rule_id", rule_id),
                "passed": bool(result.get("passed", baseline_passed)),
                "confidence": float(result.get("confidence", 0.5)),
                "reason": result.get("reason", baseline_reason),
                "evidence_turn_ids": result.get("evidence_turn_ids", []),
                "status": "ok",
            }
        except Exception as exc:
            return {
                "rule_id": rule_id,
                "passed": baseline_passed,
                "confidence": 0.35,
                "reason": f"LLM评估失败：{self._normalize_error_message(str(exc))}",
                "evidence_turn_ids": [],
                "status": "fallback",
            }

    def review_required_step(
        self,
        step_id: str,
        step_name: str,
        evidence_requirement: str,
        conversation_text: str,
        candidate_turn_ids: list[int],
        candidate_reason: str,
        judge_role: str = "general",
    ) -> dict:
        persona_text = JUDGE_PERSONAS.get(judge_role, JUDGE_PERSONAS["general"])
        prompt = f"""你是一个对话质量评估专家，请判断某个必做步骤是否已经完成。
评审角色：{persona_text}
步骤ID：{step_id}
步骤名称：{step_name}
步骤要求：{evidence_requirement}
规则候选轮次：{candidate_turn_ids}
候选理由：{candidate_reason}

对话内容：
{conversation_text}

请只返回 JSON：
{{
  "step_id": "{step_id}",
  "step_name": "{step_name}",
  "completed": <true/false>,
  "confidence": <0.0-1.0>,
  "reason": "<中文理由>",
  "evidence_turn_ids": [<相关轮次编号>]
}}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的对话质量评估专家，所有输出都必须使用中文。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=400,
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("empty response")
            result = self._safe_parse_json(content)
            return {
                "step_id": result.get("step_id", step_id),
                "step_name": result.get("step_name", step_name),
                "completed": bool(result.get("completed", False)),
                "confidence": float(result.get("confidence", 0.5)),
                "reason": result.get("reason", candidate_reason),
                "evidence_turn_ids": result.get("evidence_turn_ids", candidate_turn_ids),
                "status": "ok",
            }
        except Exception as exc:
            return {
                "step_id": step_id,
                "step_name": step_name,
                "completed": bool(candidate_turn_ids),
                "confidence": 0.35,
                "reason": f"LLM评估失败：{self._normalize_error_message(str(exc))}",
                "evidence_turn_ids": candidate_turn_ids,
                "status": "fallback",
            }

    def _extract_json(self, content: str) -> str:
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if fenced:
            return fenced.group(1).strip()
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            return content[start : end + 1]
        return content.strip()

    def _safe_parse_json(self, content: str) -> dict:
        raw = self._extract_json(content)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", raw)
            if not cleaned.rstrip().endswith("}"):
                cleaned = cleaned.rstrip().rstrip(",") + "}"
            return json.loads(cleaned)

    def _normalize_error_message(self, raw: str) -> str:
        lowered = raw.lower()
        if "blocked" in lowered:
            return "请求被拦截，请检查网关或模型权限。"
        if "timeout" in lowered:
            return "请求超时，请稍后重试。"
        if "empty response" in lowered or "empty response" in raw:
            return "模型未返回内容。"
        if "network" in lowered:
            return "网络请求失败。"
        if "connection error" in lowered:
            return "连接失败。"
        return raw
