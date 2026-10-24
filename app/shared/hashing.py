"""哈希与 ID 生成工具。"""

from __future__ import annotations

import hashlib
import uuid


def sha256_bytes(data: bytes) -> str:
    """计算字节内容 SHA-256。"""
    return hashlib.sha256(data).hexdigest()


def sha256_text(value: str) -> str:
    """计算 UTF-8 文本 SHA-256。"""
    return sha256_bytes(value.encode("utf-8"))


def uuid4_str() -> str:
    """生成标准 UUIDv4 字符串。"""
    return str(uuid.uuid4())


def deterministic_uuid(namespace: uuid.UUID, value: str) -> str:
    """基于命名空间和业务键生成稳定 UUIDv5。"""
    return str(uuid.uuid5(namespace, value))


__all__ = [
    "deterministic_uuid",
    "sha256_bytes",
    "sha256_text",
    "uuid4_str",
]
