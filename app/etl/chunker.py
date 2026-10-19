"""文档分块：固定长度 / 递归 / 按段落等策略。"""

from __future__ import annotations

from typing import Any

import tiktoken
from loguru import logger


class DocumentChunker:
    """文档分块器：支持多种策略。"""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        encoding_name: str = "cl100k_base",
    ) -> None:
        self.chunk_size = max(32, chunk_size)
        self.chunk_overlap = max(0, min(chunk_overlap, self.chunk_size - 1))
        self._encoding: Any | None
        try:
            self._encoding = tiktoken.get_encoding(encoding_name)
        except Exception as exc:
            logger.warning("tiktoken 编码不可用，回退字符切分: {}", exc)
            self._encoding = None

    def _len(self, text: str) -> int:
        if self._encoding is None:
            return len(text)
        return len(self._encoding.encode(text))

    def chunk(self, text: str) -> list[str]:
        """按生产默认的递归策略切分全文。"""
        text = text.strip()
        if not text:
            return []
        return self._chunk_recursive(text, _depth=0)

    def _chunk_fixed(self, text: str) -> list[str]:
        """按固定字符窗口切片（近似 token 长度）。"""
        out: list[str] = []
        start = 0
        n = len(text)
        while start < n:
            end = min(n, start + self.chunk_size)
            out.append(text[start:end])
            if end >= n:
                break
            start = end - self.chunk_overlap
            if start < 0:
                start = 0
        return out

    def _chunk_paragraph(self, text: str) -> list[str]:
        """按空行分段，再合并到目标长度。"""
        paras = [p.strip() for p in text.split("\n\n") if p.strip()]
        merged: list[str] = []
        buf = ""
        for p in paras:
            candidate = (buf + "\n\n" + p).strip() if buf else p
            if self._len(candidate) <= self.chunk_size:
                buf = candidate
            else:
                if buf:
                    merged.append(buf)
                buf = p
        if buf:
            merged.append(buf)
        return merged if merged else [text]

    def _chunk_recursive(
        self,
        text: str,
        separators: list[str] | None = None,
        *,
        _depth: int = 0,
    ) -> list[str]:
        """递归按分隔符切分，过长片段继续细分或退回固定窗口。"""
        if _depth > 24:
            return self._chunk_fixed(text)
        seps = separators or ["\n\n", "\n", "。", ". ", " "]
        if self._len(text) <= self.chunk_size:
            return [text]

        for i, sep in enumerate(seps):
            if sep not in text:
                continue
            pieces = [p for p in text.split(sep) if p.strip() or p == ""]
            merged: list[str] = []
            buf = ""
            for part in pieces:
                candidate = (buf + sep + part) if buf else part
                if self._len(candidate) <= self.chunk_size:
                    buf = candidate
                else:
                    if buf:
                        merged.extend(
                            self._chunk_recursive(
                                buf, seps[i + 1 :], _depth=_depth + 1
                            )
                        )
                    buf = part
            if buf:
                merged.extend(
                    self._chunk_recursive(buf, seps[i + 1 :], _depth=_depth + 1)
                )
            return merged if merged else self._chunk_fixed(text)

        return self._chunk_fixed(text)
