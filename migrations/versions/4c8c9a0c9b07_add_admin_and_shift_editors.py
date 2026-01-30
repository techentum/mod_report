"""add admin and shift editors

Revision ID: 4c8c9a0c9b07
Revises: bd2f85c198aa
Create Date: 2025-02-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4c8c9a0c9b07"
down_revision = "bd2f85c198aa"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "shift_editors",
        sa.Column("shift_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["shift_id"], ["shift.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("shift_id", "user_id"),
    )
    op.alter_column("user", "is_admin", server_default=None)


def downgrade():
    op.drop_table("shift_editors")
    op.drop_column("user", "is_admin")
