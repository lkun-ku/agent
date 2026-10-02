"""知识库目录同步回归测试：增量动作计算（纯函数）。"""

from __future__ import annotations

from app.core.rag.ingest import plan_sync


def test_new_file_marks_add() -> None:
    actions = plan_sync({"a.txt": "h1"}, {})
    assert actions == {"a.txt": "add"}


def test_changed_hash_marks_update() -> None:
    actions = plan_sync({"a.txt": "h2"}, {"a.txt": "h1"})
    assert actions == {"a.txt": "update"}


def test_unchanged_marks_skip() -> None:
    actions = plan_sync({"a.txt": "h1"}, {"a.txt": "h1"})
    assert actions == {"a.txt": "skip"}


def test_removed_file_marks_delete() -> None:
    actions = plan_sync({}, {"a.txt": "h1", "b.md": "h2"})
    assert actions == {"a.txt": "delete", "b.md": "delete"}


def test_mixed_actions() -> None:
    scanned = {"keep.txt": "h1", "new.txt": "h9", "changed.md": "h3"}
    existing = {"keep.txt": "h1", "changed.md": "h2", "gone.log": "h4"}
    actions = plan_sync(scanned, existing)
    assert actions == {
        "keep.txt": "skip",
        "new.txt": "add",
        "changed.md": "update",
        "gone.log": "delete",
    }
