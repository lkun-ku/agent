"""上传文件名与文档类型工具。"""

from __future__ import annotations

from pathlib import Path

# 上传入口允许的类型；knowledge/ 同步当前有意排除 .json，避免混入配置清单。
SUPPORTED_UPLOAD_SUFFIXES = {
    ".txt",
    ".pdf",
    ".md",
    ".markdown",
    ".csv",
    ".json",
    ".log",
}

MAX_FILENAME_LENGTH = 200


def sanitize_filename(raw: str | None) -> str:
    """清理上传文件名，阻止路径穿越、空字符与过长名称。"""
    name = (raw or "").replace("\\", "/").split("/")[-1]
    name = name.replace("\x00", "").strip()
    if not name or name in {".", ".."}:
        return "unnamed"
    return name[:MAX_FILENAME_LENGTH]


def is_supported_upload(name: str, mime: str | None) -> bool:
    """按后缀白名单或纯文本 MIME 判断上传文档是否支持。"""
    if Path(name).suffix.lower() in SUPPORTED_UPLOAD_SUFFIXES:
        return True
    return bool(mime and mime.startswith("text/") and mime != "text/html")


__all__ = [
    "SUPPORTED_UPLOAD_SUFFIXES",
    "is_supported_upload",
    "sanitize_filename",
]
