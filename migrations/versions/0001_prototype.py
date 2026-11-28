"""Create the standalone prototype tables."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision = "0001_prototype"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rooms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("nightly_rate", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "amenities", ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False
        ),
        sa.CheckConstraint("capacity > 0", name="ck_rooms_capacity"),
        sa.CheckConstraint("nightly_rate >= 0", name="ck_rooms_nightly_rate"),
    )
    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("check_in", sa.Date(), nullable=False),
        sa.Column("check_out", sa.Date(), nullable=False),
        sa.Column("guests", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("total_price", sa.Numeric(18, 2), nullable=False),
        sa.CheckConstraint("check_out > check_in", name="ck_bookings_dates"),
        sa.CheckConstraint("guests > 0", name="ck_bookings_guests"),
        sa.CheckConstraint("total_price >= 0", name="ck_bookings_total_price"),
        sa.CheckConstraint("status = 'PENDING'", name="ck_bookings_status"),
    )
    op.create_index("ix_bookings_room_dates", "bookings", ["room_id", "check_in", "check_out"])


def downgrade() -> None:
    op.drop_table("bookings")
    op.drop_table("rooms")
