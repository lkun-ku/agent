"""共享纯函数工具集回归测试。"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.shared.files import (
    SUPPORTED_UPLOAD_SUFFIXES,
    is_supported_upload,
    sanitize_filename,
)
from app.shared.hashing import deterministic_uuid, sha256_bytes, sha256_text, uuid4_str
from app.shared.http import encode_sse_done, encode_sse_event
from app.shared.jsonx import dumps_json, loads_json
from app.shared.times import retention_cutoff, seconds_iso_now, utc_now


def test_sha256_bytes_matches_stdlib() -> None:
    import hashlib

    assert sha256_bytes(b"agent") == hashlib.sha256(b"agent").hexdigest()


def test_sha256_text_is_utf8_and_stable() -> None:
    first = sha256_text("退款政策")
    second = sha256_text("退款政策")
    assert first == second
    assert first == sha256_bytes("退款政策".encode())


def test_uuid4_str_returns_parseable_uuid() -> None:
    value = uuid4_str()
    parsed = uuid.UUID(value)
    assert str(parsed) == value
    assert parsed.version == 4


def test_deterministic_uuid_is_stable_and_version_five() -> None:
    namespace = uuid.NAMESPACE_URL
    first = deterministic_uuid(namespace, "knowledge:policy.md")
    second = deterministic_uuid(namespace, "knowledge:policy.md")
    other = deterministic_uuid(namespace, "knowledge:other.md")

    assert first == second
    assert first != other
    assert uuid.UUID(first).version == 5


def test_dumps_json_keeps_chinese_readable() -> None:
    assert dumps_json({"message": "退款政策"}) == '{"message": "退款政策"}'


def test_dumps_json_sorts_keys_when_requested() -> None:
    assert dumps_json({"b": 2, "a": 1}, sort_keys=True) == '{"a": 1, "b": 2}'


def test_loads_json_accepts_empty_and_default() -> None:
    assert loads_json(None, default=[]) == []
    assert loads_json("", default={}) == {}
    assert loads_json(b"", default={}) == {}


def test_loads_json_parses_bytes_and_invalid_json_raises() -> None:
    assert loads_json(b'{"ok": true}') == {"ok": True}

    with pytest.raises(json.JSONDecodeError):
        loads_json("{invalid")


def test_sanitize_filename_blocks_path_traversal_and_bad_names() -> None:
    assert sanitize_filename(r"..\..\evil.txt") == "evil.txt"
    assert sanitize_filename("/etc/passwd") == "passwd"
    assert sanitize_filename("") == "unnamed"
    assert sanitize_filename("..") == "unnamed"
    assert sanitize_filename("\x00bad.txt") == "bad.txt"


def test_sanitize_filename_truncates_to_limit() -> None:
    assert len(sanitize_filename("x" * 500)) == 200


@pytest.mark.parametrize(
    ("name", "mime", "expected"),
    [
        ("policy.txt", None, True),
        ("policy.pdf", "application/pdf", True),
        ("policy.md", "application/octet-stream", True),
        ("policy.json", "application/json", True),
        ("policy.exe", "application/octet-stream", False),
        ("policy.html", "text/html", False),
        ("policy", "text/plain", True),
        ("policy", "application/octet-stream", False),
    ],
)
def test_is_supported_upload(name: str, mime: str | None, expected: bool) -> None:
    assert is_supported_upload(name, mime) is expected


def test_supported_upload_suffixes_are_explicit() -> None:
    assert SUPPORTED_UPLOAD_SUFFIXES == {
        ".txt",
        ".pdf",
        ".md",
        ".markdown",
        ".csv",
        ".json",
        ".log",
    }


def test_sse_event_encoding_is_stable() -> None:
    frame = encode_sse_event({"content": "退款政策", "trace_id": "trace-1"})
    expected = (
        b'data: {"content": "\xe9\x80\x80\xe6\xac\xbe\xe6\x94\xbf\xe7\xad\x96", '
        b'"trace_id": "trace-1"}\n\n'
    )
    assert frame == expected


def test_sse_done_encoding() -> None:
    assert encode_sse_done() == b'data: {"done": true}\n\n'


def test_utc_now_is_timezone_aware() -> None:
    value = utc_now()
    assert value.tzinfo is UTC
    assert datetime.now(UTC) - value < timedelta(seconds=2)


def test_retention_cutoff_uses_at_least_one_day() -> None:
    now = utc_now()
    assert retention_cutoff(0) < now
    assert retention_cutoff(-10) < now


def test_seconds_iso_now_has_second_precision() -> None:
    value = seconds_iso_now()
    assert len(value) == 19
    assert value.endswith("Z") is False
    assert datetime.fromisoformat(value).tzinfo is None


def test_shared_package_has_no_infrastructure_imports() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "shared"
    banned = {"fastapi", "sqlalchemy", "redis", "pymilvus", "openai"}
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for dependency in banned:
            assert dependency not in text, f"{path.name} 不应依赖 {dependency}"
