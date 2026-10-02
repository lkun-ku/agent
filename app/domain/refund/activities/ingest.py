"""活动层 1：单据接入。解析 v2 契约、校验字段字典、CSV 对账。

纯函数，不碰数据库；任何脏数据在进入工作流之前就失败。
"""

from __future__ import annotations

import csv
import json
import os
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from typing import Any

from app.domain.refund.common import normalize, now, to_cents
from app.domain.refund.contracts import (
    ACTION_LABELS,
    REASON_CODE_MAP,
    ActionCode,
    Dataset,
    DatasetError,
    FieldSpec,
    OrderStatus,
    Record,
    RefundScope,
    RefundType,
    ReturnStatus,
)

JSON_NAME = "refund_test_dataset_cn.json"
CSV_NAME = "refund_test_dataset_cn.csv"
DICT_NAME = "refund_field_dictionary_cn.csv"


def default_paths(data_dir: Path | None = None) -> tuple[Path, Path, Path]:
    root = data_dir or Path(os.getenv("REFUND_DATA_DIR", "data"))
    return root / JSON_NAME, root / CSV_NAME, root / DICT_NAME


def _text(value: Any, name: str) -> str:
    return str(value) if value is not None else ""


def _get(raw: dict[str, Any], key: str, required: bool = True) -> Any:
    if key not in raw or raw[key] is None:
        if required:
            raise DatasetError(f"缺少必填字段 {key}")
        return None
    return raw[key]


def _minor(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DatasetError(f"{name} 必须是整数分，收到 {value!r}")
    return value


def _flag(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "是"}
    raise DatasetError(f"{name} 必须是布尔值")


def _dt(value: Any, name: str) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return normalize(datetime.fromisoformat(str(value)))
    except ValueError as exc:
        raise DatasetError(f"{name} 时间格式错误: {value!r}") from exc


def parse_record(raw: dict[str, Any]) -> Record:
    """只解析退款判定必需字段；未知字段留在 raw 快照但不参与决策。"""
    reason_code = _text(_get(raw, "reason_code"), "reason_code")
    if reason_code not in REASON_CODE_MAP:
        raise DatasetError(f"原因码 {reason_code!r} 未在 REASON_CODE_MAP 登记")

    def enum(cls: type[Enum], key: str) -> Any:
        value = _text(_get(raw, key), key)
        try:
            return cls(value)
        except ValueError as exc:
            raise DatasetError(f"{key} 枚举值非法: {value!r}") from exc

    return Record(
        refund_id=_text(_get(raw, "refund_id"), "refund_id"),
        order_id=_text(_get(raw, "order_id"), "order_id"),
        user_id=_text(_get(raw, "user_id"), "user_id"),
        idempotency_key=_text(_get(raw, "idempotency_key"), "idempotency_key"),
        order_status=enum(OrderStatus, "order_status"),
        payment_no=_text(raw.get("payment_no", ""), "payment_no"),
        goods_fee=_minor(_get(raw, "goods_fee"), "goods_fee"),
        freight_fee=_minor(_get(raw, "freight_fee"), "freight_fee"),
        tax_fee=_minor(raw.get("tax_fee", 0), "tax_fee"),
        discount_fee=_minor(_get(raw, "discount_fee"), "discount_fee"),
        paid_fee=_minor(_get(raw, "paid_fee"), "paid_fee"),
        refundable_fee=_minor(_get(raw, "refundable_fee"), "refundable_fee"),
        refund_fee=_minor(_get(raw, "refund_fee"), "refund_fee"),
        refund_type=enum(RefundType, "refund_type"),
        refund_scope=enum(RefundScope, "refund_scope"),
        reason_code=reason_code,
        reason=REASON_CODE_MAP[reason_code],
        reason_desc=_text(raw.get("reason_desc", ""), "reason_desc"),
        return_required=_flag(_get(raw, "return_required"), "return_required"),
        return_status=enum(ReturnStatus, "return_status"),
        apply_time=_dt(_get(raw, "apply_time"), "apply_time") or now(),
        delivered_at=_dt(raw.get("delivered_at"), "delivered_at"),
        sla_deadline=_dt(raw.get("sla_deadline"), "sla_deadline"),
        evidence=tuple(str(x) for x in (raw.get("evidence") or ())),
        platform_intervened=_flag(raw.get("platform_intervened", False), "platform_intervened"),
        channel_error_code=_text(raw.get("channel_error_code", ""), "channel_error_code"),
        channel_error_message=_text(raw.get("channel_error_message", ""), "channel_error_message"),
        retry_count=int(raw.get("retry_count", 0) or 0),
        user_risk_level=_text(raw.get("user_risk_level", "LOW"), "user_risk_level"),
        user_refund_rate_30d=float(raw.get("user_refund_rate_30d", 0.0) or 0.0),
        previous_refund_id=_text(raw.get("previous_refund_id", ""), "previous_refund_id"),
        scenario=_text(_get(raw, "scenario"), "scenario"),
        scenario_name=_text(_get(raw, "scenario_name"), "scenario_name"),
        expected_action=enum(ActionCode, "expected_action"),
        after_sale_no=_text(raw.get("after_sale_no", ""), "after_sale_no"),
        item_name=_text(raw.get("item_name", ""), "item_name"),
        item_count=int(raw.get("item_count", 1) or 1),
        raw=raw,
    )


def load_fields(path: Path) -> list[FieldSpec]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return [
            FieldSpec(r["字段名"], r["数据类型"], r["是否必填"] == "是", r.get("说明", ""))
            for r in csv.DictReader(fh)
            if r.get("字段名")
        ]


def validate_fields(records: Iterable[Record], specs: list[FieldSpec]) -> list[str]:
    """必填/类型/未登记字段；类型名沿用字段字典。"""
    issues: list[str] = []
    known = {s.name for s in specs}

    def ok(dtype: str, value: Any) -> bool:
        if dtype.startswith("int"):
            return isinstance(value, int) and not isinstance(value, bool)
        if dtype.startswith("float"):
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if dtype.startswith("bool"):
            return isinstance(value, bool)
        if dtype.startswith("datetime"):
            return isinstance(value, str)
        if dtype.startswith("array"):
            return isinstance(value, list)
        return isinstance(value, str)

    for rec in records:
        raw = rec.raw
        for spec in specs:
            if spec.required and spec.name not in raw:
                issues.append(f"{rec.refund_id} 缺少 {spec.name}")
            elif (
                spec.name in raw
                and raw[spec.name] is not None
                and not ok(spec.dtype, raw[spec.name])
            ):
                issues.append(f"{rec.refund_id} {spec.name} 类型不符")
        for key in raw:
            if key not in known:
                issues.append(f"{rec.refund_id} 未登记字段 {key}")
    return issues


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return [
            {(k or "").strip(): (v or "").strip() for k, v in row.items()}
            for row in csv.DictReader(fh)
            if any((v or "").strip() for v in row.values())
        ]


def crosscheck(dataset: Dataset, rows: Iterable[dict[str, str]]) -> list[str]:
    """JSON 是权威，CSV 只是对账视图；关键金额和动作必须一致。"""
    csv_map = {r.get("退款单号", ""): r for r in rows}
    issues: list[str] = []
    for rec in dataset.records:
        row = csv_map.get(rec.refund_id)
        if row is None:
            issues.append(f"CSV 缺少 {rec.refund_id}")
            continue

        def money(key: str) -> int:
            try:
                return to_cents(Decimal(row.get(key, "0") or "0"))
            except (InvalidOperation, ValueError):
                return -1

        checks = [
            ("订单号", rec.order_id, row.get("订单号", "")),
            ("实付", rec.paid_fee, money("实付(元)")),
            ("可退", rec.refundable_fee, money("可退金额(元)")),
            ("申请", rec.refund_fee, money("申请退款(元)")),
            (
                "退款类型",
                {
                    "REFUND_ONLY": "仅退款",
                    "RETURN_AND_REFUND": "退货退款",
                    "FREIGHT_ONLY": "仅退运费",
                }[rec.refund_type.value],
                row.get("退款类型", ""),
            ),
            ("退款原因", rec.reason_label, row.get("退款原因", "")),
            ("预期动作", ACTION_LABELS[rec.expected_action.value], row.get("预期动作", "")),
        ]
        for label, expected, actual in checks:
            if expected != actual:
                issues.append(f"{rec.refund_id} {label}: JSON={expected!r} CSV={actual!r}")
    for extra in sorted(set(csv_map) - {r.refund_id for r in dataset.records}):
        issues.append(f"CSV 多出 {extra}")
    return issues


def load_dataset(
    json_path: str | Path | None = None,
    csv_path: str | Path | None = None,
    data_dir: str | Path | None = None,
) -> Dataset:
    jp, default_csv, _ = default_paths(Path(data_dir) if data_dir else None)
    jp = Path(json_path) if json_path else jp
    csv_path = Path(csv_path) if csv_path else default_csv
    payload = json.loads(jp.read_text(encoding="utf-8-sig"))
    records = [parse_record(r) for r in payload["records"]]
    ids = [r.refund_id for r in records]
    dups = {x for x in ids if ids.count(x) > 1}
    if dups:
        raise DatasetError(f"refund_id 重复: {sorted(dups)}")
    if payload.get("record_count") not in (None, len(records)):
        raise DatasetError("record_count 与实际条数不一致")
    ds = Dataset(
        payload.get("dataset_id", ""),
        payload.get("schema_version", ""),
        payload.get("amount_unit", ""),
        _dt((payload.get("source") or {}).get("produced_at"), "produced_at"),
        records,
    )
    if ds.amount_unit != "分":
        raise DatasetError("金额单位必须是分")
    if csv_path.is_file():
        ds.integrity_issues = crosscheck(ds, read_csv_rows(csv_path))
    return ds


__all__ = [
    "DICT_NAME",
    "JSON_NAME",
    "CSV_NAME",
    "crosscheck",
    "default_paths",
    "load_dataset",
    "load_fields",
    "parse_record",
    "read_csv_rows",
    "validate_fields",
]
