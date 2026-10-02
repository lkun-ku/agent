"""活动层：无状态、可独立运行的工作流步骤。

执行顺序：ingest -> eligibility -> risk -> dispatch -> workflow 执行。
"""

from app.domain.refund.activities.dispatch import decide, run_dataset, run_steps
from app.domain.refund.activities.eligibility import check_eligibility, failed_codes, tax_adjusted
from app.domain.refund.activities.ingest import (
    crosscheck,
    default_paths,
    load_dataset,
    load_fields,
    parse_record,
    read_csv_rows,
    validate_fields,
)
from app.domain.refund.activities.risk import RULES, assess, hit, rule

__all__ = [
    "RULES",
    "assess",
    "check_eligibility",
    "crosscheck",
    "decide",
    "default_paths",
    "failed_codes",
    "hit",
    "load_dataset",
    "load_fields",
    "parse_record",
    "read_csv_rows",
    "rule",
    "run_dataset",
    "run_steps",
    "tax_adjusted",
    "validate_fields",
]
