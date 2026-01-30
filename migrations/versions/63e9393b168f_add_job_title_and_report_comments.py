"""add job title and report comments

Revision ID: 63e9393b168f
Revises: 0a82e6d69392
Create Date: 2026-02-02 10:12:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "63e9393b168f"
down_revision = "0a82e6d69392"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(sa.Column("job_title", sa.String(length=120), nullable=True))

    op.create_table(
        "report_comment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shift_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["author_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["shift_id"], ["shift.id"]),
    )


def downgrade():
    op.drop_table("report_comment")

    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_column("job_title")
