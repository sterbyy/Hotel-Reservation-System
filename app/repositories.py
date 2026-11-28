from collections.abc import Sequence
from datetime import date

from sqlalchemy import exists, select
from sqlalchemy.orm import InstrumentedAttribute, Session
from sqlalchemy.sql.selectable import Exists

from app.models import Booking, BookingStatus, Payment, Room


def overlapping_booking(
    room_id: int | InstrumentedAttribute[int], check_in: date, check_out: date
) -> Exists:
    return exists().where(
        Booking.room_id == room_id,
        Booking.status.in_((BookingStatus.PENDING, BookingStatus.CONFIRMED)),
        Booking.check_in < check_out,
        Booking.check_out > check_in,
    )


class RoomRepository:
    def __init__(self, session: Session):
        self.session = session

    def search(self, check_in: date, check_out: date, guests: int) -> Sequence[Room]:
        query = (
            select(Room)
            .where(
                Room.capacity >= guests,
                ~overlapping_booking(Room.id, check_in, check_out).correlate(Room),
            )
            .order_by(Room.id)
        )
        return self.session.scalars(query).all()

    def get(self, room_id: int) -> Room | None:
        return self.session.get(Room, room_id)

    def lock(self, room_id: int) -> Room | None:
        query = select(Room).where(Room.id == room_id).with_for_update()
        return self.session.scalar(query)


class BookingRepository:
    def __init__(self, session: Session):
        self.session = session

    def overlaps(self, room_id: int, check_in: date, check_out: date) -> bool:
        query = select(overlapping_booking(room_id, check_in, check_out))
        return bool(self.session.scalar(query))

    def add(self, booking: Booking) -> None:
        self.session.add(booking)
        self.session.flush()

    def details(self, booking_id: int, token_hash: bytes) -> tuple[Booking, Payment | None] | None:
        query = (
            select(Booking, Payment)
            .outerjoin(Payment, Payment.booking_id == Booking.id)
            .where(Booking.id == booking_id, Booking.access_token_hash == token_hash)
        )
        row = self.session.execute(query).one_or_none()
        return (row.Booking, row.Payment) if row is not None else None

    def lock(self, booking_id: int, token_hash: bytes) -> Booking | None:
        credentials = (Booking.id == booking_id, Booking.access_token_hash == token_hash)
        room_query = (
            select(Room.id)
            .join(Booking, Booking.room_id == Room.id)
            .where(*credentials)
            .with_for_update(of=Room)
        )
        room_id = self.session.scalar(room_query)
        if room_id is None:
            return None

        # Re-read the booking after the room lock and recheck its room and credentials.
        query = (
            select(Booking)
            .where(*credentials, Booking.room_id == room_id)
            .with_for_update()
        )
        return self.session.scalar(query)

    def get_payment(self, booking_id: int) -> Payment | None:
        return self.session.get(Payment, booking_id)

    def add_payment(self, payment: Payment) -> None:
        self.session.add(payment)
