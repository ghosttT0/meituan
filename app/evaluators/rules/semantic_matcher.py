"""语义相似度匹配工具，用 embedding 替代关键词匹配。降级策略：embedding 不可用时回退关键词。"""
import math
from typing import Callable


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(x * x for x in b))
    return dot / norm if norm else 0.0


def _get_embed_fn() -> Callable[[list[str]], list[list[float]]] | None:
    """尝试构建 OpenAI embedding 调用函数，失败返回 None。"""
    try:
        from openai import OpenAI
        from app.core.config import get_settings
        import os
        if os.getenv("PYTEST_CURRENT_TEST"):
            return None
        settings = get_settings()
        client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)

        def embed(texts: list[str]) -> list[list[float]]:
            resp = client.embeddings.create(model="text-embedding-3-small", input=texts)
            return [item.embedding for item in resp.data]

        return embed
    except Exception:
        return None


def semantic_match(
    text: str,
    references: list[str],
    threshold: float = 0.65,
    fallback_keywords: list[str] | None = None,
) -> tuple[bool, str]:
    """
    判断 text 是否语义匹配 references 中任意一项。
    返回 (matched: bool, matched_reference: str)。
    若 embedding 不可用，退回 fallback_keywords 关键词匹配。
    """
    embed_fn = _get_embed_fn()
    if embed_fn is None:
        # 降级：关键词匹配
        for kw in (fallback_keywords or references):
            if kw in text:
                return True, kw
        return False, ""

    try:
        all_texts = [text] + references
        embeddings = embed_fn(all_texts)
        text_emb = embeddings[0]
        for i, ref_emb in enumerate(embeddings[1:]):
            score = _cosine(text_emb, ref_emb)
            if score >= threshold:
                return True, references[i]
        return False, ""
    except Exception:
        # embedding 调用失败，退回关键词
        for kw in (fallback_keywords or references):
            if kw in text:
                return True, kw
        return False, ""
