"""keep who decided on a request even if that user is deleted

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-15 03:35:25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FULL_NAME = "(SELECT trim(last_name || ' ' || first_name || ' ' || middle_name) FROM users WHERE users.id = {column})"


def upgrade() -> None:
    with op.batch_alter_table("supplements", schema=None) as batch_op:
        batch_op.add_column(sa.Column("reviewed_by_name", sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column("cancelled_by_name", sa.String(length=300), nullable=True))
        batch_op.alter_column("submitted_by", existing_type=sa.INTEGER(), nullable=True)

    op.execute(f"UPDATE supplements SET reviewed_by_name = {FULL_NAME.format(column='reviewed_by')}")
    op.execute(f"UPDATE supplements SET cancelled_by_name = {FULL_NAME.format(column='cancelled_by')}")


def downgrade() -> None:
    with op.batch_alter_table("supplements", schema=None) as batch_op:
        batch_op.alter_column("submitted_by", existing_type=sa.INTEGER(), nullable=False)
        batch_op.drop_column("cancelled_by_name")
        batch_op.drop_column("reviewed_by_name")
