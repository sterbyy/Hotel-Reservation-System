import hashlib
import secrets
from collections.abc import Callable
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.booking_events import BookingEvent, BookingEventPublisher, BookingEventType
from app.cancellation import CancellationPolicy, PaidCancellationPolicy, UnpaidCancellationPolicy
from app.models import Booking, BookingStatus, Payment, PaymentStatus
from app.payments import DemoPaymentOutcome, PaymentGatewayFactory
from app.repositories import BookingRepository, RoomRepository
from app.schemas import (
    BookingCreate,
    BookingCreatedResponse,
    BookingResponse,
    BookingStateResponse,
    PaymentResponse,
)


class RoomNotFound(Exception):
    pass


class RoomCapacityExceeded(Exception):
    pass


class RoomUnavailable(Exception):
    pass


class BookingNotFound(Exception):
    pass


class BookingConflict(Exception):
    pass


def utc_today() -> date:
    return datetime.now(UTC).date()


def token_digest(token: str | None) -> bytes:
    if token is None or len(token) != 43 or not token.isascii():
        raise BookingNotFound("Booking not found")
    return hashlib.sha256(token.encode("ascii")).digest()


def booking_state(booking: Booking, payment: Payment | None) -> BookingStateResponse:
    return BookingStateResponse(
        **BookingResponse.model_validate(booking).model_dump(),
        payment=PaymentResponse.model_validate(payment) if payment is not None else None,
    )


def booking_event(
    kind: BookingEventType, booking: Booking, payment: Payment | None = None
) -> BookingEvent:
    return BookingEvent(
        kind,
        booking.id,
        BookingStatus(booking.status),
        PaymentStatus(payment.status) if payment is not None else None,
    )


class BookingService:
    def __init__(
        self,
        gateway_factory: PaymentGatewayFactory,
        publisher: BookingEventPublisher,
        today: Callable[[], date] = utc_today,
    ):
        self.gateway_factory = gateway_factory
        self.publisher = publisher
        self.today = today
        self.cancellation_policies: dict[BookingStatus, CancellationPolicy] = {
            BookingStatus.PENDING: UnpaidCancellationPolicy(),
            BookingStatus.CONFIRMED: PaidCancellationPolicy(),
        }

    def create(self, session: Session, request: BookingCreate) -> BookingCreatedResponse:
        rooms = RoomRepository(session)
        bookings = BookingRepository(session)

        with session.begin():
            room = rooms.lock(request.room_id)
            if room is None:
                raise RoomNotFound("Room not found")
            if request.guests > room.capacity:
                raise RoomCapacityExceeded("Guest count exceeds room capacity")
            if bookings.overlaps(room.id, request.check_in, request.check_out):
                raise RoomUnavailable("Room is unavailable for the selected dates")

            token = secrets.token_urlsafe(32)
            nights = (request.check_out - request.check_in).days
            booking = Booking(
                room_id=room.id,
                check_in=request.check_in,
                check_out=request.check_out,
                guests=request.guests,
                status=BookingStatus.PENDING,
                total_price=room.nightly_rate * nights,
                access_token_hash=token_digest(token),
            )
            bookings.add(booking)
            response = BookingCreatedResponse(
                **BookingResponse.model_validate(booking).model_dump(), access_token=token
            )
            event = booking_event(BookingEventType.CREATED, booking)
        self.publisher.publish(event)
        return response

    def get(self, session: Session, booking_id: int, token: str | None) -> BookingStateResponse:
        state = BookingRepository(session).details(booking_id, token_digest(token))
        if state is None:
            raise BookingNotFound("Booking not found")
        return booking_state(*state)

    def pay(
        self, session: Session, booking_id: int, token: str | None, outcome: DemoPaymentOutcome
    ) -> BookingStateResponse:
        bookings = BookingRepository(session)
        digest = token_digest(token)
        with session.begin():
            booking = bookings.lock(booking_id, digest)
            if booking is None:
                raise BookingNotFound("Booking not found")
            if booking.status == BookingStatus.CANCELLED:
                raise BookingConflict("Cancelled booking cannot be paid")

            # Read payment in a new statement after obtaining the booking lock.
            payment = bookings.get_payment(booking.id)
            if booking.status == BookingStatus.CONFIRMED:
                if payment is None or payment.status != PaymentStatus.SUCCEEDED:
                    raise BookingConflict("Booking has an inconsistent payment state")
                if outcome == DemoPaymentOutcome.FAILED:
                    raise BookingConflict("Confirmed booking cannot be paid again")
                return booking_state(booking, payment)
            if payment is not None:
                if payment.status != PaymentStatus.FAILED:
                    raise BookingConflict("Booking has an inconsistent payment state")
                if outcome == DemoPaymentOutcome.FAILED:
                    return booking_state(booking, payment)

            gateway = self.gateway_factory.create_gateway()
            approved = gateway.charge(outcome)
            payment_status = PaymentStatus.SUCCEEDED if approved else PaymentStatus.FAILED
            if payment is None:
                payment = Payment(booking_id=booking.id, status=payment_status)
                bookings.add_payment(payment)
            else:
                payment.status = payment_status

            kind = BookingEventType.PAYMENT_FAILED
            if approved:
                booking.status = BookingStatus.CONFIRMED
                kind = BookingEventType.CONFIRMED
            event = booking_event(kind, booking, payment)
            response = booking_state(booking, payment)
        self.publisher.publish(event)
        return response

    def cancel(
        self, session: Session, booking_id: int, token: str | None
    ) -> BookingStateResponse:
        bookings = BookingRepository(session)
        digest = token_digest(token)
        with session.begin():
            booking = bookings.lock(booking_id, digest)
            if booking is None:
                raise BookingNotFound("Booking not found")
            payment = bookings.get_payment(booking.id)
            if booking.status == BookingStatus.CANCELLED:
                return booking_state(booking, payment)

            policy = self.cancellation_policies[BookingStatus(booking.status)]
            decision = policy.decide((booking.check_in - self.today()).days)
            if not decision.allowed:
                raise BookingConflict("Booking cannot be cancelled on or after check-in")
            if decision.refund:
                if payment is None or payment.status != PaymentStatus.SUCCEEDED:
                    raise BookingConflict("Booking has an inconsistent payment state")
                gateway = self.gateway_factory.create_gateway()
                payment.refunded_amount = gateway.refund(booking.total_price)
                payment.status = PaymentStatus.REFUNDED

            booking.status = BookingStatus.CANCELLED
            event = booking_event(BookingEventType.CANCELLED, booking, payment)
            response = booking_state(booking, payment)
        self.publisher.publish(event)
        return response
