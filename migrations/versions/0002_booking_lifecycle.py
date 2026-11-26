"""Add booking credentials, lifecycle states and demo payment state."""

import sqlalchemy as sa
from alembic import op

revision = "0002_booking_lifecycle"
down_revision = "0001_prototype"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("access_token_hash", sa.LargeBinary(), nullable=True))
    op.create_check_constraint(
        "ck_bookings_token_hash", "bookings", "octet_length(access_token_hash) = 32"
    )
    op.drop_constraint("ck_bookings_status", "bookings", type_="check")
    op.create_check_constraint(
        "ck_bookings_status", "bookings", "status IN ('PENDING', 'CONFIRMED', 'CANCELLED')"
    )
    op.create_table(
        "payments",
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("refunded_amount", sa.Numeric(18, 2), nullable=True),
        sa.CheckConstraint(
            "status IN ('FAILED', 'SUCCEEDED', 'REFUNDED')", name="ck_payments_status"
        ),
        sa.CheckConstraint(
            "(status = 'REFUNDED' AND refunded_amount IS NOT NULL AND refunded_amount >= 0) "
            "OR (status <> 'REFUNDED' AND refunded_amount IS NULL)",
            name="ck_payments_refund",
        ),
    )


def downgrade() -> None:
    op.execute("LOCK TABLE bookings, payments IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM payments) OR EXISTS (
                SELECT 1 FROM bookings WHERE access_token_hash IS NOT NULL OR status <> 'PENDING'
            ) THEN
                RAISE EXCEPTION 'Cannot downgrade: booking lifecycle data exists';
            END IF;
        END;
        $$;
    """)
    op.drop_table("payments")
    op.drop_constraint("ck_bookings_status", "bookings", type_="check")
    op.create_check_constraint("ck_bookings_status", "bookings", "status = 'PENDING'")
    op.drop_constraint("ck_bookings_token_hash", "bookings", type_="check")
    op.drop_column("bookings", "access_token_hash")
