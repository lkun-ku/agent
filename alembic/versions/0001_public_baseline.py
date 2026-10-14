"""public schema baseline

Revision ID: 0001_public_baseline
Revises:
Create Date: 2026-11-13

"""

from collections.abc import Sequence

from alembic import op
from app.infrastructure.database.models import Base

revision: str = "0001_public_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建 public schema 当前模型集合；已有表由 create_all 幂等跳过。"""
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    """回滚 public schema 当前模型集合；生产执行前必须备份并确认。"""
    Base.metadata.drop_all(bind=op.get_bind())
