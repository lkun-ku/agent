"""时间工具：统一 UTC 时间、保留窗口与日志展示格式。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def utc_now() -> datetime:
    """返回 timezone-aware UTC 时间。"""
    return datetime.now(UTC)


def retention_cutoff(days: int) -> datetime:
    """按保留天数计算清理截止点；天数最少为 1。"""
    return utc_now() - timedelta(days=max(1, days))


def seconds_iso_now() -> str:
    """返回秒级 ISO-8601 时间，用于诊断页展示。"""
    return datetime.now().isoformat(timespec="seconds")


__all__ = ["retention_cutoff", "seconds_iso_now", "utc_now"]
