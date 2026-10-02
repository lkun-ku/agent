"""外部工作流的 264 条数据在迁入后逐条保持一致的动作结果。"""

from __future__ import annotations

from pathlib import Path

from sqlite_store import Store

from app.core.tools.refund.service import RefundService
from app.domain.refund.activities.ingest import load_dataset

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "refund"


def test_all_datasets_keep_expected_actions(tmp_path: Path) -> None:
    paths = [DATA / "refund_test_dataset_cn.json"]
    paths.extend(sorted(DATA.glob("validation/*/refund_test_dataset_cn.json")))
    assert len(paths) == 6

    mismatches: list[str] = []
    total = 0
    for index, path in enumerate(paths):
        dataset = load_dataset(
            json_path=path,
            csv_path=path.with_suffix(".csv"),
        )
        service = RefundService(
            Store(tmp_path / f"dataset-{index}.db"),
            dataset=dataset,
        )
        try:
            for record in dataset.records:
                total += 1
                view = service.submit_record(record)
                if view.action_code != record.expected_action.value:
                    mismatches.append(
                        f"{record.refund_id}: {view.action_code} != {record.expected_action.value}"
                    )
        finally:
            service.close()

    assert total == 264
    assert not mismatches, "\n".join(mismatches[:20])
