"""上传接口回归测试：文件名安全、类型/体积校验（不依赖真实数据库）。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes.document import _is_supported, _sanitize_filename
from app.infrastructure.database.session import get_async_session
from app.main import app


class _FakeSession:
    """最小 AsyncSession 替身：只记录调用，不触达数据库。"""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        """模拟空查询结果（用于去重查找等）。"""
        from types import SimpleNamespace

        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


async def _fake_session() -> AsyncIterator[_FakeSession]:
    yield _FakeSession()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # 测试不加载嵌入模型 / 不连 Milvus：向量入库直接视为未启用
    async def _no_pipeline() -> None:
        return None

    monkeypatch.setattr("app.api.routes.document.get_pipeline", _no_pipeline)
    app.dependency_overrides[get_async_session] = _fake_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../evil.txt", "evil.txt"),
        ("..\\..\\evil.txt", "evil.txt"),
        ("/etc/passwd", "passwd"),
        ("a/b/c.pdf", "c.pdf"),
        ("", "unnamed"),
        (".", "unnamed"),
        ("..", "unnamed"),
        (None, "unnamed"),
    ],
)
def test_sanitize_filename(raw: str | None, expected: str) -> None:
    assert _sanitize_filename(raw) == expected


def test_sanitize_filename_truncates() -> None:
    assert len(_sanitize_filename("x" * 500)) == 200


@pytest.mark.parametrize(
    ("name", "mime", "supported"),
    [
        ("a.txt", "text/plain", True),
        ("a.pdf", "application/pdf", True),
        ("a.md", None, True),
        ("no_suffix", "text/plain", True),
        ("a.docx", "application/vnd.openxmlformats-officedocument", False),
        ("a.html", "text/html", False),
        ("a.exe", "application/octet-stream", False),
    ],
)
def test_is_supported(name: str, mime: str | None, supported: bool) -> None:
    assert _is_supported(name, mime) is supported


def test_upload_rejects_unsupported_type(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("a.docx", b"PK\x03\x04", "application/octet-stream")},
    )
    assert resp.status_code == 415


def test_upload_rejects_empty_file(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("a.txt", b"", "text/plain")},
    )
    assert resp.status_code == 422
    assert "为空" in resp.json()["detail"]


def test_upload_rejects_oversized_file(client: TestClient) -> None:
    # 默认上限 20MB，这里构造 21MB 内容
    payload = b"x" * (21 * 1024 * 1024)
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("big.txt", payload, "text/plain")},
    )
    assert resp.status_code == 413


def test_upload_sanitizes_filename_and_commits(client: TestClient) -> None:
    session = _FakeSession()

    async def _session_dep() -> AsyncIterator[_FakeSession]:
        yield session

    app.dependency_overrides[get_async_session] = _session_dep
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("../../escape.txt", "企业知识库内容。" * 50, "text/plain")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["filename"] == "escape.txt"
    assert body["chunk_count"] > 0
    assert session.committed is True
    # 文档 + 分块
    assert len(session.added) == 1 + body["chunk_count"]


class _FailingCommitSession(_FakeSession):
    async def commit(self) -> None:
        raise RuntimeError("db commit failed")


class _FakePipeline:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def index_document(
        self,
        *,
        doc_id: str,
        filename: str,
        chunks: list[str],
        chunk_ids: list[str],
    ) -> int:
        assert len(chunks) == len(chunk_ids)
        return len(chunks)

    async def delete_chunks(self, ids: list[str]) -> int:
        self.deleted.extend(ids)
        return len(ids)


def test_db_commit_failure_cleans_indexed_vectors(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FailingCommitSession()
    pipeline = _FakePipeline()

    async def _session_dep() -> AsyncIterator[_FailingCommitSession]:
        yield session

    async def _pipeline_dep() -> _FakePipeline:
        return pipeline

    app.dependency_overrides[get_async_session] = _session_dep
    monkeypatch.setattr("app.api.routes.document.get_pipeline", _pipeline_dep)
    try:
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("rollback.txt", "需要回滚的文档内容" * 20, "text/plain")},
        )
        assert resp.status_code == 500
        assert session.rolled_back is True
        assert pipeline.deleted
        assert len(pipeline.deleted) == len(session.added) - 1
    finally:
        app.dependency_overrides[get_async_session] = _fake_session
