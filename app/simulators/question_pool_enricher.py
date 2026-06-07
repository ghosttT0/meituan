"""LLM 驱动的问题池补充器。当关键词触发的问题总数 < 3 时调用。"""
import json
import os
import re

from app.domain.eval_spec import EvalSpec
from app.simulators.question_pool import TaskQuestionItem, TaskQuestionPool


_CACHE: dict[str, TaskQuestionPool] = {}


class QuestionPoolEnricher:
    def enrich(self, pool: TaskQuestionPool, spec: EvalSpec) -> TaskQuestionPool:
        """用 LLM 为问题池补充问题，同一 spec 只调用一次（内存缓存）。"""
        if os.getenv("PYTEST_CURRENT_TEST"):
            return pool

        cache_key = spec.spec_id
        if cache_key in _CACHE:
            cached = _CACHE[cache_key]
            return self._merge(pool, cached)

        generated = self._generate(spec)
        _CACHE[cache_key] = generated
        return self._merge(pool, generated)

    def _generate(self, spec: EvalSpec) -> TaskQuestionPool:
        try:
            from openai import OpenAI
            from app.core.config import get_settings
            settings = get_settings()
            client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)

            faq_text = "\n".join(f"- {i.raw_text}" for i in spec.faq_items) or "无"
            step_text = "\n".join(f"- {s.raw_text}" for s in spec.flow_steps) or "无"
            constraint_text = "\n".join(f"- {c.raw_text}" for c in spec.constraint_items) or "无"

            prompt = f"""你是一个外呼测试专家，需要为以下任务指令生成真实用户可能提出的追问。

任务目标：{spec.task_goal}

FAQ 知识点：
{faq_text}

流程步骤：
{step_text}

约束项：
{constraint_text}

请生成 6 条用户追问，覆盖以下三类，每类 2 条：
1. faq_questions：针对 FAQ 知识点的追问（风险、费用、差异）
2. step_questions：针对流程步骤的操作疑问（找不到、做不了）
3. objection_questions：阻碍/异议（忙、拒绝、超纲）

每条追问要口语化、贴近真实用户，不要太书面。

只返回 JSON：
{{
  "faq_questions": [{{"text": "...", "tags": ["tag1"]}}],
  "step_questions": [{{"text": "...", "tags": ["tag1"]}}],
  "objection_questions": [{{"text": "...", "tags": ["tag1"]}}]
}}"""

            response = client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=600,
            )
            content = response.choices[0].message.content or ""
            return self._parse(content)
        except Exception:
            return TaskQuestionPool()

    def _parse(self, content: str) -> TaskQuestionPool:
        try:
            m = re.search(r"\{.*\}", content, re.DOTALL)
            data = json.loads(m.group() if m else content)
            return TaskQuestionPool(
                faq_questions=[
                    TaskQuestionItem(source="llm", prompt_text=i["text"], tags=i.get("tags", []))
                    for i in data.get("faq_questions", [])
                ],
                step_questions=[
                    TaskQuestionItem(source="llm", prompt_text=i["text"], tags=i.get("tags", []))
                    for i in data.get("step_questions", [])
                ],
                objection_questions=[
                    TaskQuestionItem(source="llm", prompt_text=i["text"], tags=i.get("tags", []))
                    for i in data.get("objection_questions", [])
                ],
            )
        except Exception:
            return TaskQuestionPool()

    def _merge(self, base: TaskQuestionPool, extra: TaskQuestionPool) -> TaskQuestionPool:
        existing = {
            item.prompt_text
            for lst in (base.faq_questions, base.step_questions, base.objection_questions)
            for item in lst
        }
        base.faq_questions += [i for i in extra.faq_questions if i.prompt_text not in existing]
        base.step_questions += [i for i in extra.step_questions if i.prompt_text not in existing]
        base.objection_questions += [i for i in extra.objection_questions if i.prompt_text not in existing]
        return base
