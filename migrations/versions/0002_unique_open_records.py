"""guard against duplicate open requests and project memberships

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-15 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Close duplicates that may already exist, otherwise the unique indexes can't be created.
    # For requests the approved one is kept (then the oldest); for memberships the oldest is kept.
    op.execute(
        """
        WITH ranked AS (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY student_id, event_id ORDER BY status = 'approved' DESC, id
            ) AS rn
            FROM supplements
            WHERE status IN ('pending', 'approved')
        )
        UPDATE supplements SET
            cancel_reason = CASE WHEN status = 'approved' THEN 'Дубль заявки' ELSE cancel_reason END,
            cancelled_at = CASE WHEN status = 'approved' THEN CURRENT_TIMESTAMP ELSE cancelled_at END,
            withdrawn_at = CASE WHEN status = 'pending' THEN CURRENT_TIMESTAMP ELSE withdrawn_at END,
            status = CASE WHEN status = 'approved' THEN 'cancelled' ELSE 'withdrawn' END
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY project_id, user_id ORDER BY start_period, id) AS rn
            FROM project_members
            WHERE end_period IS NULL
        )
        UPDATE project_members SET end_period = start_period, removed_at = CURRENT_TIMESTAMP
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
        """
    )

    with op.batch_alter_table("project_members", schema=None) as batch_op:
        batch_op.create_index(
            "uq_project_members_current",
            ["project_id", "user_id"],
            unique=True,
            sqlite_where=sa.text("end_period IS NULL"),
        )
    with op.batch_alter_table("supplements", schema=None) as batch_op:
        batch_op.create_index(
            "uq_supplements_open_per_event",
            ["student_id", "event_id"],
            unique=True,
            sqlite_where=sa.text("status IN ('pending', 'approved')"),
        )


def downgrade() -> None:
    with op.batch_alter_table("supplements", schema=None) as batch_op:
        batch_op.drop_index("uq_supplements_open_per_event", sqlite_where=sa.text("status IN ('pending', 'approved')"))
    with op.batch_alter_table("project_members", schema=None) as batch_op:
        batch_op.drop_index("uq_project_members_current", sqlite_where=sa.text("end_period IS NULL"))
