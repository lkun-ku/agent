"""数据库建表（已并入统一命令行 ``app.cli``，此文件保留兼容入口）。

用法与参数见 ``python main.py init-db --help``
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["init-db"]) or 0)
