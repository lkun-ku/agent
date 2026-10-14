"""测试根 conftest：为退款测试 double 提供导入路径。"""

from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REFUND_TEST_DIR = TESTS_DIR / "refund"

if str(REFUND_TEST_DIR) not in sys.path:
    sys.path.insert(0, str(REFUND_TEST_DIR))
