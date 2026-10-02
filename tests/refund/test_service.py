"""RefundService 的端到端批量/人工路径，使用测试 SQLite 适配器。"""

from __future__ import annotations

from pathlib import Path

from sqlite_store import Store

from app.core.tools.refund.service import RefundService

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "refund"


def test_process_main_dataset(tmp_path: Path) -> None:
    service = RefundService(Store(tmp_path / "refund.db"), data_dir=DATA)
    try:
        result = service.process_batch()
        assert result["total"] == 14
        assert result["processed"] == 14
        assert result["auto_refunded"] == 3
        assert result["auto_rejected"] == 3
        assert result["held_inbound"] == 1
        assert result["manual_queued"] == 6
        assert result["deduped"] == 1
        assert result["refunded_amount"] == 201.0
    finally:
        service.close()


def test_manual_queue_and_resolve(tmp_path: Path) -> None:
    service = RefundService(Store(tmp_path / "refund.db"), data_dir=DATA)
    try:
        service.process_batch()
        tasks = service.list_review_queue()
        assert len(tasks) == 6
        first = tasks[0]
        view = service.resume_review(first["return_id"], "reject", reviewer="qa", note="test")
        assert view.return_id == first["return_id"]
    finally:
        service.close()
