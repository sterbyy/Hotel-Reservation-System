from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, Index, LargeBinary, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BookingStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class PaymentStatus(StrEnum):
    FAILED = "FAILED"
    SUCCEEDED = "SUCCEEDED"
    REFUNDED = "REFUNDED"


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (
        CheckConstraint("capacity > 0", name="ck_rooms_capacity"),
        CheckConstraint("nightly_rate >= 0", name="ck_rooms_nightly_rate"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(80))
    capacity: Mapped[int]
    nightly_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    amenities: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]")
    )


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("check_out > check_in", name="ck_bookings_dates"),
        CheckConstraint("guests > 0", name="ck_bookings_guests"),
        CheckConstraint("total_price >= 0", name="ck_bookings_total_price"),
        CheckConstraint(
            "status IN ('PENDING', 'CONFIRMED', 'CANCELLED')", name="ck_bookings_status"
        ),
        CheckConstraint("octet_length(access_token_hash) = 32", name="ck_bookings_token_hash"),
        Index("ix_bookings_room_dates", "room_id", "check_in", "check_out"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    check_in: Mapped[date]
    check_out: Mapped[date]
    guests: Mapped[int]
    status: Mapped[str] = mapped_column(String(16))
    total_price: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    access_token_hash: Mapped[bytes | None] = mapped_column(LargeBinary)


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('FAILED', 'SUCCEEDED', 'REFUNDED')", name="ck_payments_status"
        ),
        CheckConstraint(
            "(status = 'REFUNDED' AND refunded_amount IS NOT NULL AND refunded_amount >= 0) "
            "OR (status <> 'REFUNDED' AND refunded_amount IS NULL)",
            name="ck_payments_refund",
        ),
    )

    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id"), primary_key=True, autoincrement=False
    )
    status: Mapped[str] = mapped_column(String(16))
    refunded_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
