# -*- coding: utf-8 -*-
"""3.3：RAG prompt 必须按 token 预算裁剪，并且引用编号与裁剪后的上下文一致。"""

from __future__ import annotations

from typing import Any

import pytest
import tiktoken

from app.core.rag.generator import RAGGenerator
from app.models.schemas import RetrievalResult

ENC = tiktoken.get_encoding("cl100k_base")


class CapturingLLM:
    def __init__(self, answer: str = "答案见 [1]") -> None:
        self._answer = answer
        self.prompts: list[list[dict[str, str]]] = []

    async def ainvoke(self, input: Any, **kwargs: Any) -> str:
        self.prompts.append(list(input))
        return self._answer


def make_contexts(n: int, chars: int = 600) -> list[RetrievalResult]:
    base = "向量数据库支持多种索引类型，检索时需要权衡召回率、延迟与内存占用。"
    return [
        RetrievalResult(id=f"c{i}", content=(base * 20)[:chars], score=1.0 - i * 0.01)
        for i in range(1, n + 1)
    ]


@pytest.mark.asyncio
async def test_prompt_is_trimmed_to_budget() -> None:
    llm = CapturingLLM()
    generator = RAGGenerator(
        llm=llm,
        max_context_tokens=300,
        max_prompt_tokens=3500,
    )

    await generator.generate("请总结", make_contexts(10, 600), [])

    prompt = llm.prompts[0]
    tokens = sum(len(ENC.encode(m["content"])) for m in prompt)
    assert tokens <= 3500, f"prompt 仍有 {tokens} token"


@pytest.mark.asyncio
async def test_citations_map_to_trimmed_contexts() -> None:
    llm = CapturingLLM(answer="见 [1]")
    generator = RAGGenerator(llm=llm, max_context_tokens=300, max_prompt_tokens=3500)
    contexts = make_contexts(10, 600)

    response = await generator.generate("请总结", contexts, [])

    assert len(response.citations) == 1
    assert response.citations[0].index == 1
    assert response.citations[0].result_id == contexts[0].id


@pytest.mark.asyncio
async def test_duplicate_context_ids_are_deduplicated() -> None:
    llm = CapturingLLM(answer="见 [1]")
    generator = RAGGenerator(llm=llm, max_context_tokens=300, max_prompt_tokens=3500)
    contexts = make_contexts(2, 100) + make_contexts(2, 100)

    response = await generator.generate("请总结", contexts, [])

    prompt = llm.prompts[0][1]["content"]
    assert prompt.count("id=c1") == 1
    assert response.invalid_citations == []
