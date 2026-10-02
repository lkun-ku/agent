"""命令行解析回归测试（不执行命令本身）。"""

from __future__ import annotations

import pytest

from app.cli import build_parser


def test_empty_args_default_to_serve() -> None:
    args = build_parser().parse_args([])
    assert args.command == "serve"


def test_serve_flags() -> None:
    args = build_parser().parse_args(["serve", "--port", "9000", "--reload"])
    assert args.command == "serve"
    assert args.port == 9000
    assert args.reload is True


def test_check_requires_explicit_clean_confirm() -> None:
    args = build_parser().parse_args(["check", "--clean"])
    assert args.clean is True
    assert args.yes is False


def test_ask_takes_question() -> None:
    args = build_parser().parse_args(["ask", "什么是RAG"])
    assert args.question == "什么是RAG"


def test_sync_flags() -> None:
    args = build_parser().parse_args(["sync", "--force", "--no-prune"])
    assert args.force is True
    assert args.no_prune is True


def test_unknown_command_rejected() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["no-such-command"])
