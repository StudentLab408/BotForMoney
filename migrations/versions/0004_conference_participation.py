"""conference participation type: article, theses or project

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-15 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("supplements", schema=None) as batch_op:
        batch_op.alter_column(
            "project_name", new_column_name="work_title", existing_type=sa.Text(), existing_nullable=True
        )
        batch_op.add_column(sa.Column("participation", sa.String(length=20), nullable=True))

    # Until now a conference request could only name the project it was presented with.
    op.execute(
        """
        UPDATE supplements SET participation = 'project'
        WHERE work_title IS NOT NULL AND event_id IN (SELECT id FROM events WHERE kind = 'conference')
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("supplements", schema=None) as batch_op:
        batch_op.drop_column("participation")
        batch_op.alter_column(
            "work_title", new_column_name="project_name", existing_type=sa.Text(), existing_nullable=True
        )
